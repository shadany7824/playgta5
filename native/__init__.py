"""Phase 0: three.js r186 lighting ported to Python + wgpu-py on Vulkan (engine 'threejs-native', DESIGN §5.3).

Modules:
    three_math    JS-side maths three.js runs in float64 (Matrix4/Matrix3/Quaternion/Vector3/cameras), ported
    three_chunks  GLSL extracted from the vendored ShaderChunk/ShaderLib template literals; #include resolution,
                  loop unrolling and light-count substitution as in WebGLProgram.js
    program       WebGLProgram prefix/defines generation + the mechanical WebGL2 -> Vulkan GLSL 450 adapter
    device        adapter/device selection, GPU timestamps, allocation tracking
    scene         bundle -> GPU buffers, timeline ops, WebGLLights uniform packing
    shadows       WebGLShadowMap (PCFShadowMap, depth-texture maps, directional + point cube shadows)
    probe         CubeCamera + LightProbeGenerator.fromCubeRenderTarget
    render        frame loop, passes, SSAA, resolve, readback, parity output
    runner        CLI (DESIGN §4.3)

See docs/PHASE0.md for provenance, rewrite rules and every WebGL-only workaround the port drops.
"""

PORT_NAME = "three.js r186 port"
