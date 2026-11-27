# wgpu_worker.js — driver function catalog
File: `E:\gta\playgta5\mirror\playgta5.com\b\8b0b5899ed\wgpu_worker.js` (~197 KB, ~3038 lines). Line numbers from 2026-11-23; drift after each patch — re-grep the name before editing.

The worker IS the "driver": it translates RAGE engine commands from a shared ring into WebGPU calls. 163 functions.

| Function | Line | Params (start) |
|---|---|---|
| post | 42 | `msg` |
| logLine | 44 | `s` |
| mapFormat | 69 | `f, bind` |
| dumpErrors | 128 | `` |
| w32 | 147 | `addr` |
| refreshViews | 149 | `` |
| getEncoder | 158 | `` |
| endPass | 159 | `` |
| newPassSt | 161 | `` |
| flush | 168 | `reason` |
| logOnce | 179 | `key, msg` |
| vertexFormat | 190 | `dxgi` |
| makeSampler | 208 | `words` |
| wf | 225 | `w` |
| parseWgsl | 229 | `text` |
| layoutEntry | 267 | `b, stage` |
| packUniforms | 286 | `text` |
| loadShaderIndex | 314 | `` |
| fetchRetry | 327 | `url, init` |
| fetchText | 336 | `url` |
| shaderSourcesReady | 339 | `` |
| shaderIndexReady | 346 | `` |
| packBytes | 359 | `k` |
| packShader | 370 | `rec` |
| fetchShaderSource | 379 | `sh` |
| pumpShaderQueue | 409 | `` |
| prefetchShader | 418 | `sh` |
| ensureShaderSources | 423 | `` |
| a2cModule | 433 | `prog` |
| shaderProgram | 443 | `sh` |
| initDevice | 479 | `msg` |
| textureBytes | 532 | `desc` |
| createTexture | 551 | `id, dim, w, h, d, mips, arraySize, dxgi, bind, samples` |
| dumpMemBreakdown | 573 | `` |
| createBuffer | 586 | `id, size, bind, misc, stride` |
| uploadBuffer | 603 | `id, offset, size, dataOff, noOverwrite` |
| uploadTexture | 619 | `id, mip, slice, x, y, z, w, h, d, bytesPerRow, rowsPerImage,` |
| createShader | 637 | `p, n` |
| createLayout | 649 | `p` |
| layoutSlots | 659 | `els` |
| createState | 666 | `p, n` |
| createUav | 673 | `p` |
| createSrv | 678 | `p` |
| resetState | 699 | `` |
| viewFormat | 713 | `dxgi, tex` |
| targetView | 715 | `t, dxgi, mip, slice, dimension` |
| uniformAlloc | 738 | `size` |
| stageReserve | 758 | `chunk, off, n` |
| flushUniforms | 772 | `` |
| packCopy | 781 | `prog, stage` |
| dummyTexture | 834 | `b` |
| dummySampler | 846 | `cmp` |
| dummyBuffer | 851 | `binding` |
| srvView | 858 | `srv, b` |
| proxyPipeline | 900 | `kind` |
| floatToDepthProxy | 915 | `t` |
| markColorDirty | 954 | `t` |
| depthProxy | 956 | `t, kind` |
| markDepthDirty | 993 | `t` |
| internHash | 1001 | `o` |
| bindGroupLayoutFor | 1005 | `prog, stage, group` |
| depthStencilFor | 1017 | `dss, dsFormat, roDepth, roStencil` |
| blendFor | 1035 | `state, rtIndex` |
| vertexFormatBytes | 1049 | `f` |
| vertexBuffersFor | 1056 | `vs, layout, strides` |
| vertexModule | 1080 | `vsProg, flat, remap` |
| interStageRemap | 1099 | `vsProg, psProg` |
| vsOutputStruct | 1119 | `text` |
| locationsIn | 1123 | `text, stage` |
| remapLocations | 1129 | `text, stage, map` |
| pixelModule | 1135 | `psProg, a2c, remap` |
| getPipeline | 1149 | `vsObj, psObj, vsProg, psProg, layout, rtInfo, dsFormat` |
| pipelineDescFor | 1214 | `vsObj, psObj, vsProg, psProg, layout, strides, topoIdx, stri` |
| compileSync | 1266 | `c, desc, vbReq` |
| compileAsync | 1281 | `c, desc, vbReq, onDone` |
| pipelineRecipe | 1310 | `vsObj, psObj, layout, strides, topoIdx, stripFmt, blendState` |
| recipeKey | 1318 | `rc` |
| compileAhead | 1322 | `rc, key` |
| aheadStep | 1345 | `` |
| recordRecipe | 1361 | `rc, key` |
| idbOpen | 1367 | `` |
| idbList | 1370 | `db` |
| loadRecipes | 1373 | `` |
| saveRecipes | 1391 | `` |
| ensurePass | 1405 | `` |
| prepareDepthProxies | 1453 | `prog, stage` |
| proxyOk | 1478 | `e` |
| zeroVertexBuffer | 1489 | `` |
| replayBG | 1491 | `e` |
| idSources | 1498 | `prog, group` |
| boundId | 1509 | `stage, k, x` |
| readIds | 1510 | `stage, src` |
| sameIds | 1511 | `stage, src, ids` |
| stageBG | 1512 | `stage, prog, group` |
| ent | 1557 | `binding, res, off, size` |
| buildEntries | 1558 | `` |
| noteSamplerApprox | 1566 | `st, prog, slot` |
| stageBindGroup | 1574 | `stage, prog, group, bgl` |
| bgUse | 1674 | `o` |
| gpuUid | 1680 | `o` |
| trimBindGroups | 1686 | `` |
| noteApprox | 1700 | `feature, detail` |
| skipDraw | 1701 | `why` |
| setBG | 1706 | `enc, index, g` |
| isBound | 1712 | `id` |
| setScissorOnce | 1717 | `x, y, w, h` |
| doDraw | 1724 | `p` |
| dumpDraw | 1853 | `kind, count, inst, start, baseVertex, vsProg, psProg, layout` |
| probeUavs | 1878 | `` |
| probeSmallSrvs | 1897 | `` |
| probeTarget | 1922 | `` |
| dumpFrameStats | 1939 | `` |
| dumpAllTargets | 1946 | `` |
| subresourceOf | 1953 | `t, sub` |
| mipSize | 1957 | `t, mip` |
| blockBytes | 1964 | `format` |
| texelBytesOf | 1965 | `format` |
| scratch | 1972 | `size` |
| copyThroughBuffer | 1976 | `s, ss, d, ds, w, h, hasBox, l, t, dx, dy` |
| copyRegion | 1988 | `dstId, dstSub, dx, dy, dz, srcId, srcSub, hasBox, l, t, f, r` |
| copyResource | 2020 | `dstId, srcId` |
| resolve | 2037 | `dstId, dstSub, srcId, srcSub` |
| queryStore | 2059 | `q, result, seq` |
| createQuery | 2068 | `id, type, addr` |
| beginOcclusionInPass | 2075 | `` |
| endOcclusionInPass | 2083 | `` |
| beginQuery | 2086 | `id` |
| endQuery | 2093 | `id, seq` |
| pooledBuffer | 2108 | `size, usage` |
| releaseBuffer | 2112 | `b, size, usage` |
| recordResolves | 2121 | `` |
| mapResolves | 2149 | `res` |
| onSubmitted | 2164 | `` |
| counterBuffer | 2172 | `bufObj` |
| setUavCounter | 2181 | `uavId, value` |
| logCounter | 2195 | `uavId` |
| copyCounter | 2207 | `dstId, offset, uavId` |
| computePipelineFor | 2217 | `csObj, prog` |
| doDispatch | 2246 | `x, y, z` |
| clearUav | 2276 | `id, isFloat, values` |
| generateMips | 2317 | `srvId` |
| blockInfo | 2355 | `format` |
| scheduleRBFlush | 2368 | `` |
| readback | 2389 | `p` |
| clearView | 2431 | `t, mip, slice` |
| clearRT | 2435 | `id, mip, slice, r, g, b, a` |
| clearDS | 2445 | `id, mip, slice, flags, depth, stencil` |
| makeBlit | 2458 | `` |
| crc32 | 2499 | `buf` |
| encodePng | 2508 | `w, h, rgba` |
| readString | 2523 | `w, lenBytes` |
| halfToFloat | 2529 | `h` |
| screenshot | 2551 | `id, path` |
| floatStats | 2595 | `id` |
| nanReadTexel | 2639 | `t, x, y, tw, th, mip = 0` |
| nanDetail | 2659 | `bx, by, gx, gy, tw, th` |
| nanScanAfterDraw | 2674 | `` |
| present | 2710 | `id` |
| setRange | 2841 | `dst, start, n, src` |
| yieldTask | 2850 | `` |
| runCommands | 2853 | `tail, head` |
| loop | 2969 | `` |
| start | 3001 | `msg` |
