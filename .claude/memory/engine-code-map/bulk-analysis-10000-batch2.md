# Bulk analysis batch 2 — 10,000 gameplay-system functions (2026-11-23)

Static analysis of function bodies from `game.dcmp` (name prefixes: network, ped, vehicle, task, hud, audio, replay, player, camera, weapon, script, at/par containers). Honest: structural analysis, not semantic reading of each body.

## Stubs (3)
- rage_netSocket_NativeGetReceiveBufferQueueLength
- rage_parMemberPlacementVisitor_BeginStructMember
- rage_phInstBreakable_GetBrokenPartInstance

## Vtable trampolines (145)
- rage_atHashStringNamespaceSupport_ComputeHash (line 322927)
- rage_parInstanceVisitor_VisitToplevelStructure (line 390972)
- rage_parInstanceVisitor_SimpleMember (line 415691)
- rage_parInstanceVisitor_BoolMember (line 415695)
- rage_parInstanceVisitor_VecBoolVMember (line 415699)
- rage_parInstanceVisitor_Mat33VMember (line 415703)
- rage_parInstanceVisitor_BeginStructMember (line 415707)
- rage_parInstanceVisitor_BeginPointerMember (line 415712)
- rage_parInstanceVisitor_EndPointerMember (line 415718)
- rage_parInstanceVisitor_StringMember (line 415727)
- rage_parInstanceVisitor_PointerStringMember (line 415739)
- rage_parInstanceVisitor_AtStringMember (line 415743)
- rage_parInstanceVisitor_AtHashValueMember (line 415763)
- rage_parInstanceVisitor_AtWideStringMember (line 415767)
- rage_parInstanceVisitor_WidePointerStringMember (line 415779)
- rage_parInstanceVisitor_EnumMember (line 415792)
- rage_parInstanceVisitor_BitsetMember (line 415796)
- rage_parInstanceVisitor_BeginArrayMember (line 415800)
- rage_parInstanceVisitor_BeginMapMember (line 415808)
- rage_parInstanceVisitor_VisitMapMember (line 415813)
- rage_parMemberPlacementVisitor_MemberStringMember (line 423411)
- rage_parMemberPlacementVisitor_WideMemberStringMember (line 423415)
- rage_parStreamInXml_ReadEndElement_1 (line 429103)
- rage_physical_delete (line 446083)
- rage_parCguDestructor_rage_fwClipItem (line 490213)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwClipItem (line 490217)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwClipDictionaryBuildMetadata (line 490743)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwMoveDumpNode (line 501373)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwMoveDumpDof (line 502693)
- rage_parStructure_rage_parCguGetStructureCB_rage_fwMoveDumpNetwork (line 502947)
- rage_parStructure_rage_parCguGetStructureCB_rage_ropeData (line 541367)
- rage_ptxu_Decal_InitPoint (line 705785)
- rage_ptxu_Decal_UpdateFinalize (line 705907)
- rage_ptxu_DecalPool_InitPoint (line 705940)
- rage_ptxu_Light_InitPoint (line 706534)
- rage_ptxu_Liquid_InitPoint (line 707229)
- rage_ptxu_River_InitPoint (line 707286)
- rage_ptxu_ZCull_InitPoint (line 707341)
- rage_ptxu_ZCull_UpdateFinalize (line 707518)
- rage_netInterface_IsHost (line 713007)
- rage_netInterface_FlushAllLogFiles (line 713027)
- rage_netArrayHandlerBase_GetUnsyncedPlayers (line 718089)
- rage_netArrayHandlerBase_Shutdown (line 718436)
- rage_netArrayHandlerBase_IsElementSyncedWithPlayer (line 718989)
- rage_netScriptBroadcastDataHandlerBase_WriteUpdate (line 720158)
- rage_netScriptBroadcastDataHandlerBase_ReadUpdate (line 720164)
- rage_netCloudRequestHelper_Reset (line 721583)
- rage_netCloudRequestHelper_GetFileInfo (line 721792)
- rage_netCloudRequestGetFile_DoRequest (line 721950)
- rage_objectIdRequestEvent_IsInScope (line 725364)
- rage_netPlayer_IsRemote (line 725368)
- rage_netSerialiserUtils_GetAdjustedWorldExtents (line 725927)
- rage_netSerialiserUtils_GetRealMapCoords (line 725932)
- rage_netSerialiserUtils_GetAdjustedMapCoords (line 725937)
- rage_netTimeBarWrapper_PopTimer (line 726293)
- rage_netLogSplitter_WriteMessageHeader (line 729316)
- rage_netLogSplitter_WritePlayerText (line 729323)
- rage_netLogSplitter_WriteEventData (line 729330)
- rage_netLogSplitter_WriteNodeHeader (line 729337)
- rage_CNetworkSyncDataUL_32u_CNetworkSyncDataUL (line 729817)
- rage_netPlayer_GetRlPeerId (line 730645)
- rage_netObject_GetCanCloneErrorString (line 730969)
- rage_netPlayer_GetRlGamerId (line 743854)
- rage_netArrayHandlerBase_IsElementLocallyArbitrated (line 765292)
- rage_netArrayHandlerBase_IsElementRemotelyArbitrated (line 765296)
- rage_netLogSplitter_LineBreak (line 765300)
- rage_netLogSplitter_Flush (line 765307)
- rage_netLogSplitter_Disable (line 765314)
- rage_netLogSplitter_Enable (line 765321)
- rage_netObject_GetSyncTree (line 765465)
- rage_netObject_GetMinimumUpdateLevel (line 765477)
- rage_netObject_GetUpdateLevel (line 765481)
- rage_netObject_CanSynchronise (line 765496)
- rage_netGameEvent_operator (line 766018)
- rage_CNetworkSyncDataUL_32u_CNetworkSyncDataUL_14313 (line 769025)
- rage_CNetworkSyncDataUL_32u_GetCurrentStateBuffer (line 769032)
- rage_CNetworkSyncDataUL_32u_GetShadowBuffer (line 769037)
- rage_CNetworkSyncDataUL_32u_GetSyncDataUnit (line 769042)
- rage_CNetworkSyncDataUL_32u_GetBufferSize (line 769047)
- rage_grcViewport_SetCurrentWorldIdentity (line 820976)

## Complex/hot functions (2782)
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
- rage_parManager_Initialize (line 388038, 165 lines)
- rage_atMapEntry_rage_parInputFormatInfo_rage_atMap_rage_parInputFormatInfo_rage_atMapHashFn_rage_atM (line 388845, 67 lines)
- rage_parManager_Uninitialize (line 389060, 127 lines)
- rage_parManager_parManager_1 (line 389269, 114 lines)
- rage_parTree_LoadFromStream (line 389385, 46 lines)
- rage_parTree_SaveToStream (line 389433, 51 lines)
- rage_parTreeNodeUtils_FindAndResolveAllXIncludes (line 389553, 273 lines)
- rage_parTreeNode_parTreeNode (line 389944, 46 lines)
- rage_parAttribute_GetStringRepr (line 390023, 80 lines)
- rage_parManager_LoadTree (line 390181, 260 lines)
- rage_parManager_FindInputFormat (line 390443, 53 lines)
- rage_parManager_SaveTree_1 (line 390542, 44 lines)
- rage_parUtils_OpenWritableFileWithOptionalCheckout (line 390613, 57 lines)
- rage_parManager_OpenInputStream (line 390708, 78 lines)
- rage_parInstanceVisitor_VisitStructure (line 390842, 128 lines)
- rage_parManager_LoadFromStructure (line 390979, 68 lines)
- rage_parManager_LoadFromStructure_2 (line 391106, 65 lines)
- rage_parManager_CreateAndLoadAnyType (line 391189, 64 lines)
- rage_parManager_CreateAndLoadAnyType_1 (line 391255, 85 lines)
- rage_parManager_CreateAndLoadAnyType_2 (line 391381, 42 lines)
- rage_parManager_BuildTreeNodeFromStructure (line 391425, 52 lines)
- rage_parManager_SaveFromStructure (line 391574, 41 lines)
- rage_parTreeNode_FindFromXPathInternal (line 391811, 120 lines)
- rage_atArray_rage_parAttribute_0_Grow (line 392160, 72 lines)
- rage_parTreeNode_CreateStdLeaf_3 (line 392448, 93 lines)
- rage_parTreeNode_Clone (line 392882, 112 lines)
- rage_parAttributeList_CopyFrom (line 392996, 220 lines)
- rage_parTreeNode_SwapWith (line 393231, 44 lines)
- rage_parTreeNode_SortListRecursive (line 393277, 91 lines)
- rage_parMemberString_SetFromString (line 398090, 200 lines)
- rage_parMemberArray_ResizeRawArray (line 401003, 211 lines)
- rage_atArray_rage_psoRscMemberSchemaData_0_Grow (line 404116, 44 lines)
- rage_atArray_rage_psoRscEnumSchemaValueData_0_Grow (line 404251, 43 lines)
- rage_atArray_rage_psoRscBuilderInstanceSet_0_rage_atMap_rage_atArray_rage_psoRscBuilderInstanceSet_0 (line 404296, 46 lines)
- rage_atMap_rage_atMapHashFn_rage_atMapEquals_rage_atMapMemory_operator (line 404380, 47 lines)
- rage_atMap_rage_parParsableStructure_rage_atMapHashFn_rage_parParsableStructure_rage_atMapEquals_rag (line 408285, 51 lines)
- rage_parRestExpireGuid (line 408346, 51 lines)
- rage_parRestParserGuidService_ProcessCommand (line 408399, 49 lines)
- rage_parRestRegisterSingleton (line 409644, 74 lines)
- rage_parNeedsTreeForOutputVisitor_VisitStructure (line 409720, 67 lines)
- rage_parMemberStruct_CreateNewData (line 410092, 95 lines)
- rage_parMemberArray_DeleteItem (line 410248, 41 lines)
- rage_parEnumData_ValueFromName (line 410291, 91 lines)
- rage_parMemberBitset_SetFromString (line 410384, 61 lines)
- rage_parFindMemberFromUriPath_Helper (line 410514, 272 lines)
- rage_parStructure_parStructure_3632 (line 410824, 54 lines)
- rage_parStructure_BuildStructureFromStaticData (line 410880, 60 lines)
- rage_parStreamInXml_AddStaticString (line 410942, 67 lines)
- rage_atHashedMap_rage_atCaseSensitiveStringHashObj_InsertSorted (line 411072, 88 lines)
- rage_parStructure_ReadMembersFromTree (line 411162, 230 lines)
- rage_parStructure_Invoke_rage_parTreeNode (line 411394, 44 lines)
- rage_parStructure_Invoke_rage_parTreeNode_rage_parMember_rage_parParsableMember (line 411440, 46 lines)
- rage_parAttributeList_MergeFrom (line 411497, 71 lines)
- rage_parMember_LoadExtraAttributes (line 412757, 47 lines)
- rage_parMemberStruct_ReadTreeNode (line 413122, 66 lines)
- rage_parMemberString_ReadTreeNode (line 413215, 209 lines)
- rage_parMemberArray_ReadTreeNode (line 413519, 296 lines)
- rage_parMemberArray_ReadCsvDatum (line 413817, 85 lines)
- rage_parMemberEnum_parMemberEnum_3681 (line 414109, 45 lines)
- rage_parMemberBitset_GenerateStringRepr (line 414538, 254 lines)
- rage_parMemberMap_ReadTreeNode (line 414995, 139 lines)
- rage_parMemberAtBinaryMapGenericInterface_parMemberAtBinaryMapGenericInterface (line 415146, 48 lines)
- rage_parMemberAtBinaryMapGenericInterface_InsertKey (line 415271, 48 lines)
- rage_parInitVisitor_BitsetMember (line 416302, 143 lines)
- rage_parXmlWriterVisitor_SimpleMember (line 416472, 146 lines)
- rage_parXmlWriterVisitor_VecBoolVMember (line 416620, 63 lines)
- rage_parXmlWriterVisitor_Vec2VMember (line 416685, 60 lines)
- rage_parXmlWriterVisitor_Vec3VMember (line 416747, 63 lines)
- rage_parXmlWriterVisitor_Vec4VMember (line 416812, 66 lines)
- rage_parXmlWriterVisitor_Mat33VMember (line 416880, 180 lines)
- rage_parXmlWriterVisitor_Mat34VMember (line 417062, 186 lines)
- rage_parXmlWriterVisitor_Mat44VMember (line 417250, 222 lines)
- rage_parXmlWriterVisitor_Matrix34Member (line 417474, 214 lines)
- rage_parXmlWriterVisitor_Matrix44Member (line 417690, 222 lines)

## Top global writes
| Address | writes |
|---|---|
| 20221040L | 48 |
| 13346537L | 39 |
| 13346531L | 33 |
| 12317995L | 27 |
| 13048740L | 25 |
| 13059676L | 25 |
| 13346534L | 25 |
| 12317994L | 23 |
| 25957264L | 21 |
| 12317993L | 17 |
| 18581244L | 17 |
| 20219248L | 17 |
| 15411996L | 16 |
| 12318058L | 14 |
| 23154064L | 13 |
| 12287684L | 12 |
| 13120481L | 12 |
| 6714280L | 11 |
| 12288152L | 10 |
| 13346535L | 10 |
| 15305681L | 10 |
| 18563345L | 10 |
| 13346536L | 9 |
| 13121117L | 9 |
| 18563344L | 9 |
| 18912112L | 9 |
| 28501281L | 9 |
| 19662280L | 9 |
| 9777344L | 8 |
| 12288268L | 8 |
| 12287600L | 8 |
| 13346544L | 8 |
| 13351008L | 8 |
| 13120480L | 8 |
| 18563680L | 8 |
| 18563676L | 8 |
| 18581248L | 8 |
| 20192368L | 8 |
| 13347172L | 7 |
| 13347168L | 7 |
| 13347192L | 7 |
| 13347188L | 7 |
| 13351081L | 7 |
| 12321460L | 7 |
| 19223288L | 7 |
| 18563424L | 7 |
| 19234888L | 7 |
| 19658976L | 7 |
| 23389168L | 7 |
| 20234928L | 7 |
| 12316116L | 6 |
| 12318057L | 6 |
| 13118969L | 6 |
| 13070456L | 6 |
| 13352384L | 6 |
| 15524392L | 6 |
| 15562216L | 6 |
| 15562208L | 6 |
| 19223544L | 6 |
| 19223540L | 6 |

## Vtable slots
| Slot | calls |
|---|---|
| 0 | 3162 |
| 2 | 147 |
| 34 | 128 |
| 3 | 123 |
| 5 | 120 |
| 1 | 106 |
| 6 | 86 |
| 4 | 80 |
| 15 | 55 |
| 7 | 53 |
| 9 | 51 |
| 14 | 49 |
| 13 | 47 |
| 8 | 41 |
| 10 | 27 |
| 30 | 25 |
| 19 | 22 |
| 38 | 22 |
| 26 | 22 |
| 12 | 20 |
| 35 | 19 |
| 33 | 18 |
| 40 | 18 |
| 18 | 18 |
| 11 | 15 |
| 503 | 14 |
| 27 | 13 |
| 20 | 13 |
| 78 | 13 |
| 37 | 10 |

## Follow-up read
- **20221040L** (top write, 48): CPedDamageSetBase_DrawBlit (line 3331640) increments it by 4 per vertex — another immediate-mode blit vertex pointer. Consistent with batch 1 finding that the engine emits lots of immediate-mode geometry.

## Relevance to FPS
Gameplay systems decide HOW MANY entities exist and what they do; the render batch (batch 1) converts that to draws. Ped/vehicle count controls are the upstream lever for draw count but require gameplay-level changes (not safe to patch). No direct FPS patch targets identified in this batch.
