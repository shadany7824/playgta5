/*
 * threejs-web harness: drives the pinned, unmodified three.js r186 WebGL build (DESIGN §5). Nothing in
 * ./vendor/three is changed; this file only uses three.js's public API.
 *
 * web/runner.py owns the frame loop (fixed timestep, DESIGN §1) and calls, through Playwright:
 *   H.init(cfg)      build the renderer and scene from bundle.json + arrays (§4.2, §5.2); returns device info
 *                    or {skip: reason}
 *   H.beginView(a)   select a camera, reset the probe
 *   H.frame(a)       frame k: apply the timeline ops scheduled at k, (re)capture the probe, draw; on capture frames
 *                    read back (base64 Float32 RGB, row 0 = top; plus base64 RGB8 in parity mode)
 *   H.finish()       resolve outstanding GPU timer queries; return per-frame timing, memory and precompute
 */
import * as THREE from 'three';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import { LightProbeGenerator } from 'three/addons/lights/LightProbeGenerator.js';

const LINEAR = THREE.LinearSRGBColorSpace;
const now = () => performance.now();
const DTYPES = {
	float32: Float32Array, float64: Float64Array, uint32: Uint32Array, int32: Int32Array,
	uint16: Uint16Array, int16: Int16Array, uint8: Uint8Array, int8: Int8Array,
};
const SIDES = { FrontSide: THREE.FrontSide, BackSide: THREE.BackSide, DoubleSide: THREE.DoubleSide };
const COLOR_SPACES = { 'srgb': THREE.SRGBColorSpace, 'srgb-linear': THREE.LinearSRGBColorSpace };

class Skip extends Error {}

let S = null; // everything built by init()

// ------------------------------------------------------------------------------------------------ helpers

function setLinear( color, rgb ) {

	// DESIGN §5.2: colours are linear-sRGB; three.js colour management must not convert them.
	return color.setRGB( rgb[ 0 ], rgb[ 1 ], rgb[ 2 ], LINEAR );

}

function enumValue( name, what ) {

	const v = THREE[ name ];
	if ( typeof v !== 'number' ) throw new Skip( `unsupported ${what} '${name}'` );
	return v;

}

function setMatrix( obj, elements ) {

	obj.matrix.fromArray( elements ); // column-major = Matrix4.elements
	obj.matrixWorldNeedsUpdate = true; // matrixAutoUpdate is false, so three.js only recomputes matrixWorld on request

}

async function fetchOk( url ) {

	const r = await fetch( url, { cache: 'no-store' } );
	if ( ! r.ok ) throw new Error( `GET ${url}: HTTP ${r.status}` );
	return r;

}

async function loadBundle( url ) {

	const bundle = await ( await fetchOk( url ) ).json();
	const base = url.slice( 0, url.lastIndexOf( '/' ) + 1 );
	const arrays = {};
	await Promise.all( Object.entries( bundle.arrays || {} ).map( async ( [ name, spec ] ) => {

		const Ctor = DTYPES[ spec.dtype ];
		if ( ! Ctor ) throw new Skip( `array ${name}: unsupported dtype ${spec.dtype}` );
		const buf = await ( await fetchOk( base + spec.file ) ).arrayBuffer();
		const n = spec.shape.reduce( ( a, b ) => a * b, 1 );
		if ( buf.byteLength !== n * Ctor.BYTES_PER_ELEMENT ) {

			throw new Error( `array ${name}: ${buf.byteLength} bytes, expected ${n * Ctor.BYTES_PER_ELEMENT}` );

		}

		arrays[ name ] = new Ctor( buf );

	} ) );
	return { bundle, arrays };

}

function toBase64( view ) {

	const u8 = new Uint8Array( view.buffer, view.byteOffset, view.byteLength );
	if ( typeof u8.toBase64 === 'function' ) return u8.toBase64();
	let s = '';
	for ( let i = 0; i < u8.length; i += 0x8000 ) s += String.fromCharCode.apply( null, u8.subarray( i, i + 0x8000 ) );
	return btoa( s );

}

// GL row 0 is the bottom; outputs have row 0 = top (DESIGN §1). RGBA -> RGB.
function flipRGB( rgba, W, H, Ctor ) {

	const out = new Ctor( W * H * 3 );
	for ( let y = 0; y < H; y ++ ) {

		const src = ( H - 1 - y ) * W * 4, dst = y * W * 3;
		for ( let x = 0; x < W; x ++ ) {

			out[ dst + 3 * x ] = rgba[ src + 4 * x ];
			out[ dst + 3 * x + 1 ] = rgba[ src + 4 * x + 1 ];
			out[ dst + 3 * x + 2 ] = rgba[ src + 4 * x + 2 ];

		}

	}

	return out;

}

// ------------------------------------------------------------------------------------------------ scene (§5.2)

function makeGeometry( d, arrays ) {

	for ( const k of [ 'position', 'normal', 'index' ] ) {

		if ( ! arrays[ d[ k ] ] ) throw new Error( `${d.name}: missing array '${d[ k ]}'` );

	}

	const g = new THREE.BufferGeometry();
	g.setAttribute( 'position', new THREE.BufferAttribute( arrays[ d.position ], 3 ) );
	g.setAttribute( 'normal', new THREE.BufferAttribute( arrays[ d.normal ], 3 ) );
	g.setIndex( new THREE.BufferAttribute( arrays[ d.index ], 1 ) );
	return g;

}

function makeLambert( d ) {

	if ( d.type !== undefined && d.type !== 'MeshLambertMaterial' ) throw new Skip( `unsupported material type ${d.type}` );
	const side = SIDES[ d.side ?? 'DoubleSide' ];
	if ( side === undefined ) throw new Skip( `unsupported side ${d.side}` );
	const m = new THREE.MeshLambertMaterial( { side } );
	setLinear( m.color, d.color ?? [ 1, 1, 1 ] );
	setLinear( m.emissive, d.emissive ?? [ 0, 0, 0 ] );
	return m;

}

function configureShadow( light, d ) {

	light.castShadow = !! d.castShadow;
	const s = d.shadow;
	if ( ! s ) return;
	const sh = light.shadow;
	if ( s.mapSize ) sh.mapSize.set( s.mapSize[ 0 ], s.mapSize[ 1 ] );
	if ( s.bias !== undefined ) sh.bias = s.bias;
	if ( s.normalBias !== undefined ) sh.normalBias = s.normalBias;
	if ( s.radius !== undefined ) sh.radius = s.radius;
	const cam = sh.camera;
	if ( s.near !== undefined ) cam.near = s.near;
	if ( s.far !== undefined ) cam.far = s.far;
	if ( s.camera ) {

		for ( const k of [ 'left', 'right', 'top', 'bottom', 'near', 'far' ] ) if ( s.camera[ k ] !== undefined ) cam[ k ] = s.camera[ k ];

	}

	cam.updateProjectionMatrix();

}

function makeLight( d, scene ) {

	switch ( d.type ) {

		case 'PointLight': {

			const l = new THREE.PointLight();
			setLinear( l.color, d.color );
			l.intensity = d.intensity;
			l.distance = d.distance ?? 0;
			l.decay = d.decay ?? 2;
			l.position.fromArray( d.position );
			configureShadow( l, d );
			return l;

		}

		case 'DirectionalLight': {

			const l = new THREE.DirectionalLight();
			setLinear( l.color, d.color );
			l.intensity = d.intensity;
			l.position.fromArray( d.position );
			l.target.position.fromArray( d.target );
			scene.add( l.target ); // keeps target.matrixWorld current
			configureShadow( l, d );
			return l;

		}

		case 'RectAreaLight': {

			const l = new THREE.RectAreaLight();
			setLinear( l.color, d.color );
			l.intensity = d.intensity;
			l.width = d.width;
			l.height = d.height;
			l.position.fromArray( d.position );
			l.quaternion.fromArray( d.quaternion ); // [x, y, z, w]; local -Z = emitting normal
			return l;

		}

		case 'HemisphereLight': {

			const l = new THREE.HemisphereLight();
			setLinear( l.color, d.skyColor );
			setLinear( l.groundColor, d.groundColor ?? [ 0, 0, 0 ] );
			l.intensity = d.intensity;
			l.position.fromArray( d.up ?? [ 0, 0, 1 ] ); // HemisphereLight's sky direction is its position
			return l;

		}

		default:
			throw new Skip( `unsupported light type ${d.type}` );

	}

}

// ------------------------------------------------------------------------------------------------ memory

function texelBytes( tex ) {

	if ( tex.format === THREE.DepthStencilFormat ) return 4;
	const ch = { [ THREE.RGBAFormat ]: 4, [ THREE.RGFormat ]: 2, [ THREE.RedFormat ]: 1, [ THREE.DepthFormat ]: 1 }[ tex.format ] ?? 4;
	const b = {
		[ THREE.FloatType ]: 4, [ THREE.HalfFloatType ]: 2, [ THREE.UnsignedByteType ]: 1, [ THREE.UnsignedIntType ]: 4,
		[ THREE.UnsignedShortType ]: 2, [ THREE.UnsignedInt248Type ]: 4,
	}[ tex.type ] ?? 4;
	return ch * b;

}

function rtBytes( rt ) {

	if ( ! rt ) return 0;
	const faces = rt.isWebGLCubeRenderTarget ? 6 : 1;
	const px = rt.width * rt.height * faces;
	let bytes = 0;
	for ( const t of ( rt.textures ?? [ rt.texture ] ) ) bytes += px * texelBytes( t );
	if ( rt.depthTexture ) bytes += px * texelBytes( rt.depthTexture );
	else if ( rt.depthBuffer ) bytes += px * 4; // DEPTH_COMPONENT24 renderbuffer(s)
	return bytes;

}

function memoryReport() {

	const { W, H, renderer, scene } = S;
	const items = {
		canvas: W * H * 8, // RGBA8 drawing buffer + 24-bit depth
		ssaa_sample_target: rtBytes( S.sampleRT ),
		ssaa_accum_target: rtBytes( S.accumRT ),
	};
	if ( S.cubeRT ) items.probe_cube_target = rtBytes( S.cubeRT );
	for ( const l of S.lightList ) {

		if ( l.shadow && l.shadow.map ) items[ `shadow_map:${l.name}` ] = rtBytes( l.shadow.map );

	}

	if ( S.hasRect ) {

		const fl = S.renderer.extensions.has( 'OES_texture_float_linear' );
		const t1 = fl ? THREE.UniformsLib.LTC_FLOAT_1 : THREE.UniformsLib.LTC_HALF_1;
		const t2 = fl ? THREE.UniformsLib.LTC_FLOAT_2 : THREE.UniformsLib.LTC_HALF_2;
		items.ltc_tables = t1.image.data.byteLength + t2.image.data.byteLength;

	}

	let tex = 0;
	for ( const v of Object.values( items ) ) tex += v;
	let buf = 0;
	const seen = new Set();
	const addGeometry = ( g ) => {

		if ( seen.has( g ) ) return;
		seen.add( g );
		for ( const a of Object.values( g.attributes ) ) buf += a.array.byteLength;
		if ( g.index ) buf += g.index.array.byteLength;

	};

	scene.traverse( ( o ) => {

		if ( o.isMesh ) addGeometry( o.geometry );

	} );
	addGeometry( S.quad.geometry );
	const info = renderer.info;
	return {
		gpu_texture_bytes: tex, gpu_buffer_bytes: buf, texture_items: items,
		estimate: 'computed from the render targets, shadow maps, LTC tables and geometry this page allocated',
		renderer_info: { geometries: info.memory.geometries, textures: info.memory.textures, programs: ( info.programs || [] ).length },
	};

}

// ------------------------------------------------------------------------------------------------ GPU timing

function gpuBegin() {

	if ( ! S.timer ) return null;
	const gl = S.gl;
	const q = gl.createQuery();
	gl.beginQuery( S.timer.TIME_ELAPSED_EXT, q );
	return q;

}

function gpuEnd( q ) {

	if ( q ) S.gl.endQuery( S.timer.TIME_ELAPSED_EXT );

}

// Collect finished TIME_ELAPSED queries; returns true when nothing is outstanding.
function pollQueries() {

	if ( ! S.timer ) return true;
	const gl = S.gl;
	const disjoint = gl.getParameter( S.timer.GPU_DISJOINT_EXT );
	if ( disjoint ) S.disjointEvents ++;
	const still = [];
	for ( const rec of S.pending ) {

		let open = false;
		for ( const [ pass, q ] of Object.entries( rec.queries ) ) {

			if ( q === null ) continue;
			if ( disjoint ) {

				rec.gpu[ pass ] = null;
				rec.disjoint = true;

			} else if ( gl.getQueryParameter( q, gl.QUERY_RESULT_AVAILABLE ) ) {

				rec.gpu[ pass ] = gl.getQueryParameter( q, gl.QUERY_RESULT ) / 1e6; // ns -> ms

			} else {

				open = true;
				continue;

			}

			gl.deleteQuery( q );
			rec.queries[ pass ] = null;

		}

		if ( open ) still.push( rec );

	}

	S.pending = still;
	return still.length === 0;

}

// ------------------------------------------------------------------------------------------------ passes

function clearAccum() {

	const r = S.renderer;
	r.setRenderTarget( S.accumRT );
	r.setClearColor( 0x000000, 0 );
	r.clear( true, false, false );

}

// Measurement main pass: one render per SSAA offset into the FloatType target, each added with weight 1/n into the
// accumulation target (GPU additive blend, or CPU when EXT_float_blend is missing and the frame is captured).
// offsets === null renders one sample without a view offset (parity mode's linear capture).
function renderMeasure( cam, offsets, capture ) {

	const { renderer, W, H } = S;
	const list = offsets ?? [ null ];
	const gpuResolve = S.floatBlend;
	let cpuAcc = null;
	if ( gpuResolve ) {

		clearAccum();
		S.resolveMat.uniforms.weight.value = 1 / list.length;

	} else if ( capture ) {

		cpuAcc = new Float64Array( W * H * 4 );

	}

	const tmp = cpuAcc ? new Float32Array( W * H * 4 ) : null;
	for ( const off of list ) {

		if ( off !== null ) cam.setViewOffset( W, H, off[ 0 ], off[ 1 ], W, H );
		renderer.setRenderTarget( S.sampleRT );
		renderer.render( S.scene, cam );
		if ( gpuResolve ) {

			renderer.setRenderTarget( S.accumRT );
			renderer.autoClear = false;
			renderer.render( S.quadScene, S.quadCam );
			renderer.autoClear = true;

		} else if ( cpuAcc ) {

			renderer.readRenderTargetPixels( S.sampleRT, 0, 0, W, H, tmp );
			for ( let i = 0; i < tmp.length; i ++ ) cpuAcc[ i ] += tmp[ i ];

		}

	}

	if ( offsets !== null ) cam.clearViewOffset();
	renderer.setRenderTarget( null );
	if ( cpuAcc ) {

		const out = new Float32Array( W * H * 4 );
		for ( let i = 0; i < out.length; i ++ ) out[ i ] = cpuAcc[ i ] / list.length;
		S.cpuResult = out;

	}

}

function readMeasure() {

	const { W, H } = S;
	let px = S.cpuResult;
	S.cpuResult = null;
	if ( ! px ) {

		px = new Float32Array( W * H * 4 );
		S.renderer.readRenderTargetPixels( S.accumRT, 0, 0, W, H, px );

	}

	return flipRGB( px, W, H, Float32Array );

}

// Parity main pass: exactly how three.js draws to a canvas (tone mapping + sRGB output in the material shaders).
function renderCanvas( cam ) {

	S.renderer.setRenderTarget( null );
	S.renderer.render( S.scene, cam );

}

function readCanvas() {

	const { gl, W, H } = S;
	const px = new Uint8Array( W * H * 4 );
	S.renderer.setRenderTarget( null );
	gl.readPixels( 0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, px );
	return flipRGB( px, W, H, Uint8Array );

}

// Probe pass (§5.1): CubeCamera at the camera position, LightProbeGenerator.fromCubeRenderTarget. 'probe' captures with
// the probe's intensity 0 (one bounce); 'probe_dynamic' keeps the previous probe active (multi-bounce feedback).
async function captureProbe( cam ) {

	const { probe, cubeCam, cubeRT, renderer } = S;
	if ( ! S.probeChecked ) for ( let i = 0; i < 8 && S.gl.getError() !== S.gl.NO_ERROR; i ++ ); // drain stale errors
	if ( ! S.probeDynamic ) probe.intensity = 0;
	cubeCam.position.copy( cam.position );
	cubeCam.updateMatrixWorld();
	const q = gpuBegin();
	cubeCam.update( renderer, S.scene );
	gpuEnd( q );
	const generated = await LightProbeGenerator.fromCubeRenderTarget( renderer, cubeRT );
	if ( ! S.probeChecked ) {

		// A failed readPixels (e.g. HALF_FLOAT not readable on some GPUs) would silently leave the probe at zero.
		const err = S.gl.getError();
		if ( err !== S.gl.NO_ERROR ) throw new Error( `probe cube readback failed (GL error 0x${err.toString( 16 )})` );
		S.probeChecked = true;

	}

	probe.sh.copy( generated.sh );
	probe.intensity = 1;
	S.probeCaptures ++;
	return q;

}

function applyOp( op ) {

	switch ( op.op ) {

		case 'light': {

			const l = S.lightsByName[ op.name ];
			if ( ! l ) throw new Error( `timeline: no light ${op.name}` );
			if ( op.color ) setLinear( l.color, op.color );
			if ( op.intensity !== undefined ) l.intensity = op.intensity;
			if ( op.emissive && S.emittersByName[ op.name ] ) setLinear( S.emittersByName[ op.name ].material.emissive, op.emissive );
			if ( op.background ) setLinear( S.scene.background, op.background );
			break;

		}

		case 'matrix': {

			const m = S.meshesByName[ op.mesh ];
			if ( ! m ) throw new Error( `timeline: no mesh ${op.mesh}` );
			setMatrix( m, op.matrix );
			break;

		}

		case 'material': {

			const mat = S.materialsByName[ op.name ];
			if ( ! mat ) throw new Error( `timeline: no material ${op.name}` );
			setLinear( mat.color, op.color );
			break;

		}

		default:
			throw new Error( `timeline: unknown op ${op.op}` );

	}

}

// ------------------------------------------------------------------------------------------------ API

async function init( cfg ) {

	try {

		return await initInner( cfg );

	} catch ( e ) {

		if ( e instanceof Skip ) return { skip: e.message };
		throw e;

	}

}

async function initInner( cfg ) {

	const t0 = now();
	if ( new Uint8Array( new Uint16Array( [ 1 ] ).buffer )[ 0 ] !== 1 ) throw new Skip( 'big-endian platform' );
	const { bundle, arrays } = await loadBundle( cfg.bundleUrl );
	const ed = bundle.engine_data;
	if ( bundle.engine !== 'threejs' ) throw new Error( `bundle engine is '${bundle.engine}', expected 'threejs'` );
	if ( String( ed.three_revision ) !== THREE.REVISION ) {

		throw new Skip( `bundle wants three.js r${ed.three_revision}, the vendored build is r${THREE.REVISION}` );

	}

	const W = bundle.image.width, H = bundle.image.height;
	const parity = !! cfg.parity;
	const canvas = document.getElementById( 'c' );
	let renderer;
	try {

		renderer = new THREE.WebGLRenderer( {
			canvas, antialias: false, alpha: false, preserveDrawingBuffer: true,
			powerPreference: cfg.powerPreference || 'default',
		} );

	} catch ( e ) {

		throw new Skip( `WebGL2 unavailable: ${e.message}` );

	}

	renderer.setPixelRatio( 1 );
	renderer.setSize( W, H, false );
	const gl = renderer.getContext();
	if ( ! renderer.extensions.has( 'EXT_color_buffer_float' ) ) throw new Skip( 'EXT_color_buffer_float unavailable (FloatType render targets)' );
	const floatBlend = cfg.gpuResolve !== false && gl.getExtension( 'EXT_float_blend' ) !== null;
	const timing = bundle.measure?.timing !== false;
	const timer = timing ? gl.getExtension( 'EXT_disjoint_timer_query_webgl2' ) : null;

	const R = ed.renderer;
	renderer.shadowMap.enabled = true;
	renderer.shadowMap.type = enumValue( R.shadowMapType, 'shadowMapType' );
	// Shadow maps are view independent: render them once per frame (needsUpdate at frame start), not once per
	// renderer.render() call (SSAA samples and cube faces would otherwise redraw them every call).
	renderer.shadowMap.autoUpdate = false;
	if ( parity ) {

		renderer.toneMapping = enumValue( R.parity.toneMapping, 'toneMapping' );
		renderer.toneMappingExposure = R.parity.exposure;
		const cs = COLOR_SPACES[ R.parity.outputColorSpace ];
		if ( cs === undefined ) throw new Skip( `unsupported outputColorSpace ${R.parity.outputColorSpace}` );
		renderer.outputColorSpace = cs;

	} else {

		renderer.toneMapping = THREE.NoToneMapping;
		renderer.outputColorSpace = LINEAR;

	}

	// Scene
	const scene = new THREE.Scene();
	scene.background = setLinear( new THREE.Color(), ed.background ?? [ 0, 0, 0 ] );
	const materialsByName = {};
	for ( const [ name, d ] of Object.entries( ed.materials ) ) materialsByName[ name ] = makeLambert( d );
	const meshesByName = {};
	for ( const d of ed.meshes ) {

		const mat = materialsByName[ d.material ];
		if ( ! mat ) throw new Error( `mesh ${d.name}: no material ${d.material}` );
		const mesh = new THREE.Mesh( makeGeometry( d, arrays ), mat );
		mesh.name = d.name;
		mesh.matrixAutoUpdate = false;
		setMatrix( mesh, d.matrix );
		mesh.castShadow = d.castShadow !== false;
		mesh.receiveShadow = d.receiveShadow !== false;
		scene.add( mesh );
		meshesByName[ d.name ] = mesh;

	}

	const emittersByName = {};
	for ( const d of ed.emitters ?? [] ) {

		const mat = makeLambert( { type: 'MeshLambertMaterial', color: d.color, emissive: d.emissive, side: d.side } );
		const mesh = new THREE.Mesh( makeGeometry( d, arrays ), mat );
		mesh.name = d.name;
		mesh.matrixAutoUpdate = false;
		setMatrix( mesh, d.matrix );
		mesh.castShadow = d.castShadow !== false;
		mesh.receiveShadow = d.receiveShadow !== false;
		scene.add( mesh );
		emittersByName[ d.name ] = mesh;

	}

	const lightsByName = {};
	const lightList = [];
	let hasRect = false;
	for ( const d of ed.lights ) {

		const l = makeLight( d, scene );
		l.name = d.name;
		hasRect = hasRect || l.isRectAreaLight === true;
		scene.add( l );
		lightsByName[ d.name ] = l;
		lightList.push( l );

	}

	const tLtc = now();
	if ( hasRect ) RectAreaLightUniformsLib.init();
	const ltcSeconds = ( now() - tLtc ) / 1000;

	const cameras = {};
	for ( const [ name, c ] of Object.entries( ed.cameras ) ) {

		const cam = new THREE.PerspectiveCamera( c.fov, W / H, c.near, c.far );
		cam.position.fromArray( c.position );
		cam.up.fromArray( c.up ?? [ 0, 0, 1 ] );
		cam.lookAt( new THREE.Vector3().fromArray( c.lookAt ) );
		cam.updateMatrixWorld();
		cameras[ name ] = cam;

	}

	// Probe (§5.1)
	const P = ed.probe ?? { enabled: false };
	let probe = null, cubeRT = null, cubeCam = null;
	if ( P.enabled ) {

		probe = new THREE.LightProbe();
		probe.intensity = 1;
		scene.add( probe );
		cubeRT = new THREE.WebGLCubeRenderTarget( P.cubeSize, { type: enumValue( P.type, 'probe texture type' ) } );
		cubeCam = new THREE.CubeCamera( P.near, P.far, cubeRT );

	}

	// Measurement targets and the SSAA resolve quad
	const rtOpts = {
		type: THREE.FloatType, format: THREE.RGBAFormat, colorSpace: LINEAR, minFilter: THREE.NearestFilter,
		magFilter: THREE.NearestFilter, generateMipmaps: false, depthBuffer: true, stencilBuffer: false,
	};
	const sampleRT = new THREE.WebGLRenderTarget( W, H, rtOpts );
	const accumRT = new THREE.WebGLRenderTarget( W, H, { ...rtOpts, depthBuffer: false } );
	const resolveMat = new THREE.ShaderMaterial( {
		name: 'ssaa_resolve',
		uniforms: { src: { value: sampleRT.texture }, weight: { value: 1 } },
		vertexShader: 'void main() { gl_Position = vec4( position.xy, 0.0, 1.0 ); }',
		fragmentShader: 'uniform sampler2D src; uniform float weight;\n' +
			'void main() { gl_FragColor = texelFetch( src, ivec2( gl_FragCoord.xy ), 0 ) * weight; }',
		blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
		blendEquationAlpha: THREE.AddEquation, blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneFactor,
		depthTest: false, depthWrite: false, toneMapped: false,
	} );
	const quad = new THREE.Mesh( new THREE.PlaneGeometry( 2, 2 ), resolveMat );
	quad.frustumCulled = false;
	const quadScene = new THREE.Scene();
	quadScene.add( quad );
	const quadCam = new THREE.OrthographicCamera( - 1, 1, 1, - 1, 0, 1 );

	const events = ( ed.timeline?.events ?? [] ).slice().sort( ( a, b ) => a.frame - b.frame );

	S = {
		bundle, ed, W, H, parity, renderer, gl, scene, cameras, materialsByName, meshesByName, emittersByName,
		lightsByName, lightList, hasRect, probe, cubeRT, cubeCam, probeDynamic: !! P.dynamic, probeChecked: false,
		probeCaptures: 0, sampleRT, accumRT, resolveMat, quad, quadScene, quadCam, floatBlend, timer,
		offsets: R.ssaa_offsets, events, nextEvent: 0, cam: null, viewStart: true, records: [], pending: [],
		disjointEvents: 0, cpuResult: null, framesRendered: 0,
	};
	const tBuilt = now();

	// Shader compilation up front, so it is precompute rather than frame time.
	const tCompile = now();
	const compileFor = async ( target ) => {

		renderer.setRenderTarget( target );
		for ( const cam of Object.values( cameras ) ) await renderer.compileAsync( scene, cam );
		renderer.setRenderTarget( accumRT );
		await renderer.compileAsync( quadScene, quadCam );

	};

	await compileFor( sampleRT );
	if ( parity ) await compileFor( null );
	renderer.setRenderTarget( null );
	const compileSeconds = ( now() - tCompile ) / 1000;

	let ltcBytes = 0;
	if ( hasRect ) {

		const fl = renderer.extensions.has( 'OES_texture_float_linear' );
		ltcBytes = ( fl ? THREE.UniformsLib.LTC_FLOAT_1 : THREE.UniformsLib.LTC_HALF_1 ).image.data.byteLength +
			( fl ? THREE.UniformsLib.LTC_FLOAT_2 : THREE.UniformsLib.LTC_HALF_2 ).image.data.byteLength;

	}

	S.precompute = {
		seconds: ( tBuilt - t0 ) / 1000 + compileSeconds,
		bytes: ltcBytes,
		items: {
			bundle_load_and_scene_build_s: ( tBuilt - t0 ) / 1000, shader_compile_s: compileSeconds,
			ltc_tables_bytes: ltcBytes, ltc_init_s: ltcSeconds, programs: ( renderer.info.programs || [] ).length,
		},
	};

	const dbg = gl.getExtension( 'WEBGL_debug_renderer_info' );
	const caps = renderer.capabilities;
	return {
		ok: true,
		three_revision: THREE.REVISION,
		webgl: {
			renderer: dbg ? gl.getParameter( dbg.UNMASKED_RENDERER_WEBGL ) : gl.getParameter( gl.RENDERER ),
			vendor: dbg ? gl.getParameter( dbg.UNMASKED_VENDOR_WEBGL ) : gl.getParameter( gl.VENDOR ),
			version: gl.getParameter( gl.VERSION ),
			glsl: gl.getParameter( gl.SHADING_LANGUAGE_VERSION ),
			extensions: gl.getSupportedExtensions(),
			precision: caps.precision, max_texture_size: caps.maxTextureSize,
			context_attributes: gl.getContextAttributes(),
		},
		float_blend: floatBlend,
		timer_query: !! timer,
		user_agent: navigator.userAgent,
		cross_origin_isolated: self.crossOriginIsolated === true,
		device_pixel_ratio: window.devicePixelRatio,
		precompute: S.precompute,
	};

}

function beginView( a ) {

	const cam = S.cameras[ a.camera ];
	if ( ! cam ) throw new Error( `no camera ${a.camera}` );
	S.cam = cam;
	S.viewStart = true;
	if ( S.probe ) {

		S.probe.sh.zero(); // every view starts from an empty probe (deterministic, order independent)
		S.probe.intensity = 1;

	}

	return { camera: a.camera };

}

async function frame( a ) {

	const t0 = now();
	const cam = S.cam;
	if ( ! cam ) throw new Error( 'frame() before beginView()' );

	// Timeline ops scheduled at or before this frame (DESIGN §1: frame k applies its actions, then draws).
	let applied = 0;
	while ( S.nextEvent < S.events.length && S.events[ S.nextEvent ].frame <= a.frame ) {

		for ( const op of S.events[ S.nextEvent ].ops ) applyOp( op );
		applied ++;
		S.nextEvent ++;

	}

	S.renderer.shadowMap.needsUpdate = true; // first render() of this frame redraws the shadow maps

	let qProbe = null, probeCaptured = false;
	if ( S.probe && ( S.probeDynamic || S.viewStart || applied > 0 ) ) {

		qProbe = await captureProbe( cam );
		probeCaptured = true;

	}

	S.viewStart = false;

	const qMain = gpuBegin();
	if ( S.parity ) renderCanvas( cam );
	else renderMeasure( cam, S.offsets, !! a.capture );
	gpuEnd( qMain );
	const cpuMs = now() - t0;

	const out = { cpu_ms: cpuMs, probe_captured: probeCaptured, events_applied: applied };
	let readbackMs = null;
	if ( a.capture ) {

		const t1 = now();
		if ( S.parity ) {

			out.png = toBase64( readCanvas() );
			renderMeasure( cam, null, true ); // the same single sample, linear, into the float target
			out.rgb = toBase64( readMeasure() );

		} else {

			out.rgb = toBase64( readMeasure() );

		}

		readbackMs = now() - t1;
		out.readback_ms = readbackMs;

	}

	const rec = {
		frame: a.frame, station: a.station ?? null, warmup: !! a.warmup, captured: !! a.capture,
		probe_captured: probeCaptured, cpu_ms: cpuMs, readback_ms: readbackMs,
		gpu: { main: null, probe: probeCaptured ? null : 0.0 }, queries: { main: qMain, probe: qProbe }, disjoint: false,
	};
	S.records.push( rec );
	if ( qMain || qProbe ) S.pending.push( rec );
	S.framesRendered ++;
	pollQueries();
	return out;

}

async function finish( a = {} ) {

	const timeoutMs = a.timeoutMs ?? 10000;
	const t0 = now();
	while ( ! pollQueries() && now() - t0 < timeoutMs ) await new Promise( ( r ) => setTimeout( r, 4 ) );
	let resolved = 0;
	const frames = S.records.map( ( r ) => {

		for ( const [ pass, q ] of Object.entries( r.queries ) ) {

			if ( q ) {

				S.gl.deleteQuery( q );
				r.queries[ pass ] = null;

			}

		}

		const ok = S.timer && r.gpu.main !== null && r.gpu.probe !== null;
		if ( ok ) resolved ++;
		const f = {
			frame: r.frame, station: r.station, warmup: r.warmup, captured: r.captured, probe_captured: r.probe_captured,
			cpu_ms: r.cpu_ms, gpu_ms: ok ? r.gpu.main + r.gpu.probe : null,
			passes: S.timer ? { main: r.gpu.main, probe: r.gpu.probe } : {},
		};
		if ( r.readback_ms !== null ) f.readback_ms = r.readback_ms;
		if ( r.disjoint ) f.disjoint = true;
		return f;

	} );
	return {
		frames, gpu_timestamps: !! S.timer && resolved > 0, gpu_resolved_frames: resolved,
		disjoint_events: S.disjointEvents, memory: memoryReport(), precompute: S.precompute,
		probe_captures: S.probeCaptures, frames_rendered: S.framesRendered,
	};

}

window.H = { ready: true, revision: THREE.REVISION, init, beginView, frame, finish };
