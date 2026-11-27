# Bulk analysis of 10000 engine functions (2026-11-23)

Programmatic parse of `game.dcmp` function bodies — classified structure, NOT semantic reading of every line. Selected by render/FPS-relevant name prefixes (rage_grc, rage_dl, rage_fw, CLod, streaming, CSettings, CTimeCycle, RageDirect3D, Draw, Render, Cull, Visibility, vehicle/ped/entity). Honest: this is static analysis, not understanding each function.

## Stub functions (return 0, no real work) — 4
- wasm_null_d3d_NullAdapter_CheckInterfaceSupport
- wasm_null_d3d_NullSwapChain_GetDesc
- sfRenderer_CreateTextureYUV
- CPoliceRidersDispatch_GetIsEntityValidForOrder

## One-line vtable trampolines — 300
- wasm_null_d3d_NullSwapChain_GetDevice (line 302665)
- wasm_null_d3d_NullSwapChain_GetBuffer (line 302749)
- wasm_null_d3d_NullSwapChain_NullSwapChain (line 302836)
- wasm_null_d3d_NullSwapChain_NullSwapChain_457 (line 302843)
- wasm_null_d3d_DevChild_wasm_null_d3d_Stub_ID3D11Texture2D_GetDevice (line 302900)
- wasm_null_d3d_NullDevice_GetImmediateContext (line 304890)
- wasm_null_d3d_NullView_wasm_null_d3d_Stub_ID3D11ShaderResourceView_D3D11_SHADER_RESOURCE_VIEW_DESC_G (line 305480)
- wasm_null_d3d_NullView_wasm_null_d3d_Stub_ID3D11ShaderResourceView_D3D11_SHADER_RESOURCE_VIEW_DESC_N (line 305568)
- wasm_null_d3d_NullView_wasm_null_d3d_Stub_ID3D11ShaderResourceView_D3D11_SHADER_RESOURCE_VIEW_DESC_N_1 (line 305575)
- wasm_null_d3d_NullView_wasm_null_d3d_Stub_ID3D11UnorderedAccessView_D3D11_UNORDERED_ACCESS_VIEW_DESC_1 (line 305665)
- wasm_null_d3d_NullView_wasm_null_d3d_Stub_ID3D11UnorderedAccessView_D3D11_UNORDERED_ACCESS_VIEW_DESC_2 (line 305672)
- wasm_null_d3d_NullView_wasm_null_d3d_Stub_ID3D11RenderTargetView_D3D11_RENDER_TARGET_VIEW_DESC_NullV (line 305679)
- wasm_null_d3d_NullRTV_NullRTV (line 305686)
- wasm_null_d3d_NullView_wasm_null_d3d_Stub_ID3D11DepthStencilView_D3D11_DEPTH_STENCIL_VIEW_DESC_NullV (line 305717)
- wasm_null_d3d_NullDSV_NullDSV (line 305724)
- wasm_null_d3d_NullQuery_GetDataSize (line 306122)
- wasm_null_d3d_NullContext_OMSetRenderTargetsAndUnorderedAccessViews (line 308155)
- rage_atHashStringNamespaceSupport_ComputeHash (line 322927)
- rage_FunctionTranslator1_rage_fwEntity_thunk (line 483318)
- rage_parCguDestructor_rage_fwClipItem (line 490213)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwClipItem (line 490217)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwClipDictionaryBuildMetadata (line 490743)
- rage_AppendBinMapFreeObjectPtr_rage_fwClipSet (line 495332)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwMoveDumpNode (line 501373)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwMoveDumpDof (line 502693)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwMoveDumpNetwork (line 502947)
- rage_fwAnimDirectorComponentMotionTree_ShutdownPoolClass (line 508329)
- rage_fwAnimDirectorComponentCreature_ShutdownPoolClass (line 508611)
- rage_fwAnimDirectorComponentMove_ShutdownPoolClass (line 509229)
- rage_fwAnimDirectorComponentExpressions_ShutdownPoolClass (line 509613)
- rage_fwAnimDirectorComponentRagDoll_ShutdownPoolClass (line 509827)
- rage_fwAnimDirectorComponentSyncedScene_ShutdownPoolClass (line 509999)
- rage_fwAnimDirectorComponentFacialRig_ShutdownPoolClass (line 513455)
- rage_fwDynamicEntityComponent_DeleteAnimDirector (line 520007)
- rage_fwDrawData_fwDrawData (line 522581)
- rage_fwDrawData_fwDrawData_7252 (line 522588)
- rage_fwDrawData_Update (line 522604)
- rage_fwEntity_SetPosition (line 526030)
- rage_dlCmdBeginDraw_ExecuteStatic (line 526940)
- rage_dlCmdEndDraw_ExecuteStatic (line 526945)
- rage_dlCmdLockRenderTarget_ExecuteStatic (line 526950)
- rage_dlCmdPushTimebar_ExecuteStatic (line 527045)
- rage_dlCmdPopTimebar_ExecuteStatic (line 527049)
- rage_dlCmdPushMarker_ExecuteStatic (line 527107)
- rage_dlCmdPopMarker_ExecuteStatic (line 527111)
- rage_dlCmdSetGeometryVertexOffsets_ExecuteStatic (line 527115)
- rage_dlCmdSetArrayView_ExecuteStatic (line 527172)
- rage_dlCmdCallBackNoArg_ExecuteStatic (line 527177)
- rage_dlCmdGenericArgBase_ExecuteStatic (line 527185)
- rage_dlCmdPushTimebar_dlCmdPushTimebar (line 530789)
- rage_dlCmdPopTimebar_dlCmdPopTimebar (line 530796)
- rage_T_CbGeneric5ArgsExecutor_bool_rage_dlDrawListMgr_eHighestDrawableLOD_rage_dlDrawListMgr_eHighes (line 532122)
- rage_fwPropInstanceListDef_ReleaseDeviceResources (line 553096)
- rage_grcInstanceBufferBasic_Lock (line 576417)
- rage_grcInstanceBufferBasic_Unlock (line 576423)
- rage_fwAssetRscStore_rage_crClipDictionary_rage_fwClipDictionaryDef_SetResource (line 576551)
- rage_T_CbGeneric2ArgsExecutor_rage_grcDebugDraw_LingerBuffer_Execute (line 577430)
- rage_T_CbGeneric1ArgExecutor_rage_grcDebugDraw_LingerBuffer_Execute (line 577434)
- rage_grcBufferedStaticInstanceBufferList_3_GetFirst (line 578893)
- rage_ptxu_ZCull_InitPoint (line 707341)
- rage_ptxu_ZCull_UpdateFinalize (line 707518)
- rage_fwAudioEntity_PreUpdateService (line 712152)
- rage_fwAudioEntity_HandleAnimEvent (line 712182)
- rage_grmModel_Draw (line 795757)
- rage_grmModel_DrawSkinned (line 795763)
- rage_wasm_cb_M_rage_pfDrawItemBase_EnabledStateChanged_0_thunk (line 809019)
- rage_wasm_cb_M_rage_pfDrawItemSlider_SliderValueChanged_0_thunk (line 809323)
- rage_wasm_cb_M_rage_pfDrawItemSliderInt_SliderValueChanged_0_thunk (line 809347)
- rage_wasm_cb_M_rage_pfDrawItemSliderFull_SliderValueChanged_0_thunk (line 809372)
- rage_pfDrawGroup_EnableChildren (line 809529)
- rage_pfDrawGroup_DisableChildren (line 809533)
- rage_wasm_cb_M_rage_pfDrawManager_AddWidgets_1_thunk (line 809549)
- rage_grmGeometry_DirectDraw (line 809621)
- rage_grcTexture_RunCustomLoadFunc (line 810710)
- rage_grcTextureReferenceBase_Copy (line 817480)
- rage_grcTextureReferenceBase_IsSRGB (line 817486)
- rage_grcTextureReferenceBase_LockRect (line 817492)
- rage_grcTextureReferenceBase_UnlockRect (line 817498)
- rage_grcTextureReferenceBase_GetTexturePtr (line 817503)
- rage_grcTextureReferenceBase_GetTexturePtr_1 (line 817509)
- rage_grcTextureReferenceBase_GetWidth (line 817547)
- rage_grcTextureReferenceBase_GetDepth (line 817553)
- rage_grcTextureReferenceBase_GetMipMapCount (line 817559)
- rage_grcTextureReferenceBase_GetArraySize (line 817565)
- rage_grcTextureReferenceBase_GetBitsPerPixel (line 817571)
- rage_grcTextureReferenceBase_GetHeight (line 817577)
- rage_grcTextureReferenceBase_Download (line 817583)
- rage_grcTextureReferenceBase_GetDownloadSize (line 817588)
- rage_grcTextureReferenceBase_IsValid (line 817594)
- rage_grcTextureReference_GetReference (line 817605)
- rage_grcTextureReference_SetEffectInfo (line 817611)
- rage_grcViewport_SetCurrentWorldIdentity (line 820976)
- rage_grcTextureFactoryString_GetBackBuffer_1 (line 830321)
- rage_grcTextureFactoryString_GetFrontBufferDepth (line 830325)
- grcimg_custom_error_exit (line 846772)
- rage_grcFragmentProgram_grcFragmentProgram (line 848258)
- rage_grcFragmentProgram_grcFragmentProgram_16096 (line 848265)
- rage_grcComputeProgram_grcComputeProgram (line 848272)
- rage_grcComputeProgram_grcComputeProgram_16099 (line 848279)
- rage_grcDomainProgram_grcDomainProgram (line 848286)
- rage_grcDomainProgram_grcDomainProgram_16102 (line 848293)
- rage_grcGeometryProgram_grcGeometryProgram (line 848300)
- rage_grcGeometryProgram_grcGeometryProgram_16105 (line 848307)
- rage_grcHullProgram_grcHullProgram (line 848314)
- rage_grcHullProgram_grcHullProgram_16108 (line 848321)
- rage_grcCBuffer_UnlockDirect (line 854219)
- rage_grcDevice_DisableScissor (line 856086)
- rage_grcDevice_CopyStructureCount (line 856276)
- rage_grcDevice_EndCreateVertices (line 856833)
- rage_grcDevice_SetIndices (line 856887)
- rage_grcDevice_DestroyOcclusionQuery (line 857239)
- rage_grcDevice_BeginOcclusionQuery (line 857245)
- rage_grcDevice_EndOcclusionQuery (line 857250)
- rage_grcDevice_BeginConditionalRender (line 857276)
- rage_grcDevice_EndConditionalRender (line 857281)
- rage_grcTextureFactoryPC_GetBackBuffer (line 857820)
- rage_grcTextureFactoryPC_GetFrontBuffer (line 857824)
- rage_grcTextureFactoryPC_GetFrontBufferDepth (line 857828)
- rage_grcTextureFactoryPC_GetBackBufferDepth (line 857832)
- rage_grcTextureDX11_GetBitsPerPixel (line 860221)
- ... and 180 more

## Complex / hot-looking functions (>40 lines, call_indirect or loops) — 2752
- wasm_streaming_report (line 295069, 64 lines)
- rage_grcDevice_RegisterDeviceLostCallbacks (line 301325, 68 lines)
- wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture1D_D3D11_TEXTURE1D_DESC_StorageSize (line 301452, 78 lines)
- non_virtual_thunk_to_wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture1D_D3D11_TEXTURE1D_D (line 301554, 78 lines)
- wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture1D_D3D11_TEXTURE1D_DESC_SubLayout (line 301634, 52 lines)
- non_virtual_thunk_to_wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture1D_D3D11_TEXTURE1D_D_1 (line 301688, 52 lines)
- wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture2D_D3D11_TEXTURE2D_DESC_StorageSize (line 301746, 43 lines)
- non_virtual_thunk_to_wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture2D_D3D11_TEXTURE2D_D (line 301791, 43 lines)
- wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture2D_D3D11_TEXTURE2D_DESC_SubLayout (line 301836, 57 lines)
- wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture3D_D3D11_TEXTURE3D_DESC_StorageSize (line 301906, 104 lines)
- wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture3D_D3D11_TEXTURE3D_DESC_SubLayout (line 302018, 51 lines)
- wasm_null_d3d_GpuUploadTexture (line 302101, 81 lines)
- wasm_null_d3d_NullResource_wasm_null_d3d_Stub_ID3D11Texture2D_D3D11_TEXTURE2D_DESC_GpuCreate (line 302184, 48 lines)
- wasm_null_d3d_D3D11CreateDeviceAndSwapChain (line 302336, 72 lines)
- wasm_null_d3d_NullOutput_GetDisplayModeList (line 302543, 43 lines)
- wasm_null_d3d_NullSwapChain_Present (line 302671, 76 lines)
- wasm_null_d3d_NullDevice_CreateBuffer (line 303151, 72 lines)
- wasm_null_d3d_NullDevice_CreateTexture1D (line 303225, 106 lines)
- wasm_null_d3d_NullDevice_CreateTexture2D (line 303333, 79 lines)
- wasm_null_d3d_NullDevice_CreateTexture3D (line 303414, 111 lines)
- wasm_null_d3d_NullDevice_CreateShaderResourceView (line 303527, 157 lines)
- wasm_null_d3d_NullDevice_CreateUnorderedAccessView (line 303686, 124 lines)
- wasm_null_d3d_NullDevice_CreateRenderTargetView (line 303812, 70 lines)
- wasm_null_d3d_NullDevice_CreateDepthStencilView (line 303884, 71 lines)
- wasm_null_d3d_NullDevice_CreateInputLayout (line 303957, 201 lines)
- wasm_null_d3d_NullDevice_CreateVertexShader (line 304160, 301 lines)
- wasm_null_d3d_NullContext_SetCBuffers (line 306399, 123 lines)
- wasm_null_d3d_NullContext_SetSrvs (line 306528, 68 lines)
- wasm_null_d3d_NullContext_SetSamplerStates (line 306649, 68 lines)
- wasm_null_d3d_NullContext_Map (line 306755, 187 lines)
- wasm_null_d3d_NullContext_IASetVertexBuffers (line 307549, 69 lines)
- wasm_null_d3d_NullContext_ChangedSlots (line 307620, 80 lines)
- wasm_null_d3d_NullContext_GetData (line 307932, 126 lines)
- wasm_null_d3d_NullContext_SetUavs (line 308160, 53 lines)
- wasm_null_d3d_GpuReadback (line 308673, 119 lines)
- wasm_null_d3d_NullContext_CopyResource (line 308794, 217 lines)
- wasm_null_d3d_NullContext_UpdateSubresource (line 309013, 202 lines)
- rage_atString_Replace (line 321199, 151 lines)
- rage_atString_Split (line 321352, 154 lines)
- rage_atString_Split_2 (line 321694, 378 lines)
- rage_atArray_rage_atString_0_Grow (line 322074, 114 lines)
- rage_atString_TrimLeft (line 322216, 60 lines)
- rage_atString_Split_3 (line 322278, 359 lines)
- rage_atString_Serialize (line 322673, 43 lines)
- rage_atHashStringNamespaceSupport_ShutdownNamespaces (line 322778, 49 lines)
- rage_atHashStringNamespaceSupport_ShutdownNamespace (line 322829, 96 lines)
- rage_atHashStringNamespaceSupport_AddString (line 322932, 59 lines)
- rage_atMap_rage_atMapHashFn_rage_atMapEquals_rage_atMapMemory_Recompute (line 323030, 71 lines)
- rage_atHashStringNamespaceSupport_SaveHashStrings (line 323130, 162 lines)
- rage_atHashStringNamespaceSupport_InitNamespaces (line 323294, 88 lines)
- rage_bkToggleVal_rage_atBitSet_RemoteHandler (line 326209, 111 lines)
- rage_atMapEntry_rage_ConstString_rage_atFunctor3_rage_atFunctor1_rage_atMap_rage_ConstString_rage_at (line 331825, 143 lines)
- rage_bkColor_DrawLocal (line 337518, 148 lines)
- rage_bkVector_DrawLocal (line 338591, 79 lines)
- rage_bkMatrix_DrawLocal (line 339792, 146 lines)
- rage_bkToggleVal_rage_atBitSet_RemoteCreate (line 354752, 51 lines)
- rage_atArray_rage_atBinaryMap_rage_atString_DataPair_0_Grow (line 367887, 83 lines)
- rage_atArray_rage_atBinaryMap_rage_atFinalHashString_DataPair_0_Grow (line 371958, 65 lines)
- sort4_abi_nqn220108_ClassicAlgPolicy_bool_rage_atBinaryMap_rage_atFinalHashString_DataPair_0 (line 381620, 52 lines)
- sort_heap_abi_nqn220108_ClassicAlgPolicy_bool_rage_atBinaryMap_rage_atFinalHashString_DataPair (line 381712, 65 lines)
- rage_atBinaryMap_rage_atFinalHashString_DataPair_partition_with_equals_on_left_abi_nqn220108_Classic (line 381779, 49 lines)
- pair_rage_atBinaryMap_rage_atFinalHashString_DataPair_bool_partition_with_equals_on_right_abi_nqn220 (line 381830, 55 lines)
- bool_insertion_sort_incomplete_abi_nqn220108_ClassicAlgPolicy_bool_rage_atBinaryMap_rage_atFinalHash (line 381887, 167 lines)
- enable_if_is_move_constructible_rage_atBinaryMap_rage_Mount_DataPair_value_is_move_assignable_rage_a (line 382056, 175 lines)
- sort4_abi_nqn220108_ClassicAlgPolicy_bool_rage_atBinaryMap_rage_Mount_DataPair_0 (line 382233, 41 lines)
- bool_insertion_sort_incomplete_abi_nqn220108_ClassicAlgPolicy_bool_rage_atBinaryMap_rage_Mount_DataP (line 382276, 315 lines)
- rage_atMapEntry_rage_parInputFormatInfo_rage_atMap_rage_parInputFormatInfo_rage_atMapHashFn_rage_atM (line 388845, 67 lines)
- rage_atArray_rage_parAttribute_0_Grow (line 392160, 72 lines)
- rage_atArray_rage_psoRscMemberSchemaData_0_Grow (line 404116, 44 lines)
- rage_atArray_rage_psoRscEnumSchemaValueData_0_Grow (line 404251, 43 lines)
- rage_atArray_rage_psoRscBuilderInstanceSet_0_rage_atMap_rage_atArray_rage_psoRscBuilderInstanceSet_0 (line 404296, 46 lines)
- rage_atMap_rage_atMapHashFn_rage_atMapEquals_rage_atMapMemory_operator (line 404380, 47 lines)
- rage_atMap_rage_parParsableStructure_rage_atMapHashFn_rage_parParsableStructure_rage_atMapEquals_rag (line 408285, 51 lines)
- rage_atHashedMap_rage_atCaseSensitiveStringHashObj_InsertSorted (line 411072, 88 lines)
- rage_atBinaryMap_rage_parDelegateHolderBase_DataPair_partial_sort_impl_abi_nqn220108_ClassicAlgPolic (line 433772, 137 lines)
- bool_insertion_sort_incomplete_abi_nqn220108_ClassicAlgPolicy_bool_rage_atBinaryMap_rage_parDelegate (line 433911, 200 lines)
- sort5_abi_nqn220108_ClassicAlgPolicy_bool_rage_atBinaryMap_rage_parDelegateHolderBase_DataPair_0 (line 434113, 85 lines)
- rage_atPartialStringHash (line 435228, 51 lines)
- rage_atStringHash (line 435281, 55 lines)
- rage_atDelegator1_rage_sysServiceEvent_RemoveDelegate (line 442409, 45 lines)
- rage_atMap_rage_sysStackCollector_TagEntry_rage_atMapHashFn_rage_atMapEquals_rage_atMapMemory_rage_s (line 444020, 44 lines)
- rage_sysStackCollector_TagEntry_rage_atMap_rage_sysStackCollector_TagEntry_rage_atMapHashFn_rage_atM (line 444066, 48 lines)
- rage_sysStackCollector_StackEntry_rage_atMap_rage_sysStackCollector_StackEntry_rage_atMapHashFn_rage (line 444319, 77 lines)
- rage_atMap_rage_atMapHashFn_rage_atMapEquals_rage_atMapMemory_operator_1 (line 444398, 47 lines)
- rage_atDelegator1_rage_sysServiceEvent_Dispatch (line 445544, 51 lines)
- rage_atPoolBase_Init (line 455000, 48 lines)
- rage_atPoolBase_Init_1 (line 455088, 43 lines)
- rage_atPackedSequence_InitAndCreate (line 463152, 101 lines)
- rage_atMapEntry_rage_crFrameData_rage_atMap_rage_crFrameData_rage_atMapHashFn_rage_atMapEquals_rage_ (line 470213, 47 lines)
- rage_crCreatureComponentShaderVars_DrawUpdate (line 478363, 50 lines)
- rage_atMapEntry_rage_datOwner_rage_crAnimation_DeclareStruct (line 481304, 63 lines)
- rage_fwAnimDirector_Init (line 481754, 189 lines)
- rage_fwAnimDirector_AddComponent (line 481945, 76 lines)
- rage_fwAnimDirector_InitMidPhysicsMotionTree (line 482023, 301 lines)
- rage_fwAnimDirector_AddExpression (line 483064, 160 lines)
- rage_fwAnimDirector_Shutdown (line 483266, 50 lines)
- rage_fwAnimDirector_fwAnimDirector (line 483359, 41 lines)
- rage_fwAnimDirector_UpdateMove (line 483411, 64 lines)
- rage_fwAnimDirectorComponentMotionTree_PreDelegate (line 483477, 53 lines)
- rage_fwAnimDirector_UpdateVelocityAndAngularVelocity (line 483608, 249 lines)
- rage_fwAnimDirectorComponentMove_SwapOutputBuffers (line 483859, 107 lines)
- rage_fwAnimDirector_StartUpdateMidPhysics (line 483968, 44 lines)
- rage_fwAnimDirector_StartUpdatePreRender (line 484078, 53 lines)
- rage_fwMoveNetworkInterface_UpdateAudioAndTriggeredFacialEvents (line 484152, 93 lines)
- rage_fwAnimDirector_FindPropertyInMoveNetworks (line 484247, 281 lines)
- rage_fwAnimDirector_FindScriptVisiblePropertyInPhaseRange (line 484732, 179 lines)
- rage_fwAnimDirector_RetrieveClip (line 484913, 138 lines)
- rage_fwClipSet_GetClip (line 485053, 60 lines)
- rage_fwClipSet_GetClipDictionary (line 485159, 50 lines)
- rage_fwAnimDirector_RetrieveExpression (line 485211, 80 lines)
- rage_fwAnimDirector_RetrieveFilter (line 485399, 72 lines)
- rage_fwAnimDirector_RetrieveTransitionFilter (line 485473, 72 lines)
- rage_fwAnimDirectorComponentExpressions_Init (line 485640, 147 lines)
- rage_fwAnimDirector_PoseSkeletonUsingRagdollFrame (line 486428, 69 lines)
- rage_fwAnimDirector_EnumDOFMapFilesCallback (line 486518, 187 lines)
- rage_fwAnimDirector_InitStatic (line 486707, 335 lines)
- rage_fwAnimDirectorComponentSyncedScene_ResizeSyncedScenePool (line 487693, 71 lines)
- rage_fwAnimDirector_ShutdownStatic (line 487766, 199 lines)
- rage_fwAnimDirector_Queue_Pop (line 488635, 71 lines)
- rage_fwAnimHelpers_GetMoverTrackRotationDelta (line 488943, 83 lines)

## Global addresses most written by these functions
| Address | writes |
|---|---|
| 12484544L | 72 |
| 12484536L | 61 |
| 12483660L | 51 |
| 8324232L | 45 |
| 18581244L | 43 |
| 12432384L | 34 |
| 8350528L | 32 |
| 8350548L | 32 |
| 12433376L | 31 |
| 8324208L | 30 |
| 8324216L | 30 |
| 12484464L | 29 |
| 12484548L | 28 |
| 12433348L | 27 |
| 12374288L | 21 |
| 12321496L | 19 |
| 28501281L | 19 |
| 12618128L | 18 |
| 25957264L | 18 |
| 12321460L | 16 |
| 12623360L | 16 |
| 12433364L | 16 |
| 12382196L | 16 |
| 11011980L | 15 |
| 12374284L | 15 |
| 12374960L | 15 |
| 12009688L | 14 |
| 11547056L | 13 |
| 12617352L | 13 |
| 6639512L | 13 |
| 19339458L | 13 |
| 6974204L | 13 |
| 12372616L | 12 |
| 12432816L | 12 |
| 12432424L | 11 |
| 6988156L | 11 |
| 10872608L | 10 |
| 11011832L | 10 |
| 18563345L | 10 |
| 19339457L | 10 |
| 12432408L | 9 |
| 18563344L | 9 |
| 19566063L | 9 |
| 11010953L | 8 |
| 11011268L | 8 |
| 11011848L | 8 |
| 11011840L | 8 |
| 11079768L | 8 |
| 11079772L | 8 |
| 12484552L | 8 |
| 12618136L | 8 |
| 15893512L | 8 |
| 18563680L | 8 |
| 18563676L | 8 |
| 19275256L | 8 |
| 19538308L | 8 |
| 11012112L | 7 |
| 12382488L | 7 |
| 6639488L | 7 |
| 15581304L | 7 |
| 15788988L | 7 |
| 15895428L | 7 |
| 19223288L | 7 |
| 18563424L | 7 |
| 19421928L | 7 |
| 19658976L | 7 |
| 8324224L | 6 |
| 6611092L | 6 |
| 11011896L | 6 |
| 12631152L | 6 |
| 12624016L | 6 |
| 12372136L | 6 |
| 12617336L | 6 |
| 12637360L | 6 |
| 15524392L | 6 |
| 15936026L | 6 |
| 15803890L | 6 |
| 15893528L | 6 |
| 18581248L | 6 |
| 19223544L | 6 |

## Vtable slots most called
| Slot | calls |
|---|---|
| 0 | 2885 |
| 1 | 205 |
| 2 | 179 |
| 3 | 129 |
| 4 | 102 |
| 5 | 74 |
| 13 | 72 |
| 7 | 67 |
| 6 | 58 |
| 9 | 52 |
| 8 | 50 |
| 15 | 48 |
| 10 | 37 |
| 30 | 35 |
| 21 | 32 |
| 19 | 30 |
| 14 | 29 |
| 22 | 24 |
| 64 | 23 |
| 16 | 21 |
| 11 | 20 |
| 12 | 18 |
| 23 | 17 |
| 20 | 16 |
| 35 | 16 |
| 27 | 15 |
| 25 | 14 |
| 28 | 14 |
| 34 | 14 |
| 33 | 13 |
| 50 | 12 |
| 29 | 12 |
| 24 | 11 |
| 18 | 11 |
| 78 | 11 |
| 90 | 11 |
| 26 | 10 |
| 47 | 9 |
| 38 | 8 |
| 503 | 8 |



## Follow-up read: what the top globals actually are
- **12484544L / 12484536L / 12484548L**: debug/stat counters and the immediate-mode vertex buffer pointer. 
age_grcVertex(a..i) (func9562, line ~817394) writes **36-byte vertex records** to a growable buffer: k = tls_base+1136 -> obj; j = k[16]; k[16] = j + 36; j.i/j.h/j.g = .... 
age_grcBegin/
age_grcSetup_EndDraw/
age_grcCompositeRenderTargetHelper_DrawFullScreenTri reset 12484544L=0 and set 12484548L to a primitive-type code (3/5). So 12484544 = vertex/draw counter for immediate-mode batches, 12484536 = buffer pointer, 12484548 = primitive type. Not FPS levers themselves, but confirms the engine does immediate-mode vertex emission (could be a source of many small draws).
- Top 30 global-write counts are mostly grc/streaming state, not directly tunable.
## Interpretation
- Globals with many writes are engine state; if a render-related global is written per-frame/per-entity, it is a candidate for a runtime memory-write optimization (no wasm recompile).
- Vtable slot 12 = DrawIndexed, 13 = Draw, 37 = LOD override (from earlier reads).
- Stubs/trampolines are not worth optimizing; complex functions with loops + atomics are the real work.
