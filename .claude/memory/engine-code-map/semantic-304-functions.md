# Semantic map of the verified 30,280-line region (304 functions)

Source: `verified-30000-lines.txt` (dcmp 5,001,192–5,054,474, SHA256 4da47378…). For EACH function I extracted: its role (from name), the functions it CALLS, the global addresses it touches, and vtable/loop/atomic counts. This is semantic signal derived from the actual body text — not just static counts. Role labels are heuristic; called-function lists are exact.

## Subsystem groups (180)

- **CTaskMotionInAutomobile**: 21 functions

- **CTaskMountThrowProjectile**: 16 functions

- **CTaskMotionOnBicycle**: 13 functions

- **CTaskAttachedVehicleAnimDebug**: 12 functions

- **CTaskVehicleMountedWeapon**: 12 functions

- **CTaskVehicleGun**: 11 functions

- **CTaskMotionInVehicle**: 9 functions

- **CTaskVehicleFSM**: 7 functions

- **CTaskMoveGoToVehicleDoor**: 7 functions

- **CTaskVehicleProjectile**: 6 functions

- **CTaskCloseVehicleDoorFromOutside**: 5 functions

- **CTaskRideTrain**: 5 functions

- **CTaskExitVehicleSeat**: 4 functions

- **CTaskTryToGrabVehicleDoor**: 4 functions

- **CTaskReactToBeingJacked**: 3 functions

- **CVehicleHullAI**: 3 functions

- **CTaskMotionOnBicycleController**: 3 functions

- **CTaskVehicleFSM_TransformRelativeOffsetsToWorldSpace**: 1 functions

- **CTaskVehicleFSM_ApplyGroundAndOrientationFixup**: 1 functions

- **CTaskVehicleFSM_ApplyMoverFixup**: 1 functions

- **CTaskCloseVehicleDoorFromOutside_CTaskCloseVehicleDoorFromOutside_1**: 1 functions

- **CTaskCloseVehicleDoorFromOutside_CTaskCloseVehicleDoorFromOutside_123298**: 1 functions

- **CTaskReactToBeingJacked_CTaskReactToBeingJacked**: 1 functions

- **CTaskReactToBeingJacked_CTaskReactToBeingJacked_1**: 1 functions

- **CTaskReactToBeingJacked_CTaskReactToBeingJacked_123312**: 1 functions

- **cxx_global_array_dtor_4360**: 1 functions

- **CTaskReactToBeingAskedToLeaveVehicle_CTaskReactToBeingAskedToLeaveVehicle_1**: 1 functions

- **CTaskReactToBeingAskedToLeaveVehicle_CTaskReactToBeingAskedToLeaveVehicle_123325**: 1 functions

- **CTaskReactToBeingAskedToLeaveVehicle**: 1 functions

- **CTaskGoToCarDoorAndStandStill_CTaskGoToCarDoorAndStandStill_1**: 1 functions

- **CTaskGoToCarDoorAndStandStill_CTaskGoToCarDoorAndStandStill_123332**: 1 functions

- **CTaskGoToCarDoorAndStandStill**: 1 functions

- **CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor**: 1 functions

- **CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_1**: 1 functions

- **non_virtual_thunk_to_CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor**: 1 functions

- **CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_123344**: 1 functions

- **non_virtual_thunk_to_CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_123345**: 1 functions

- **CTaskMoveGoToVehicleDoor_AdjustPosForVehicleSpeed**: 1 functions

- **CTaskMoveGoToVehicleDoor_ChooseGoToDoorMBR**: 1 functions

- **CTaskMoveGoToVehicleDoor_WarpIfPossible**: 1 functions

- **CVehicleHullCalculator**: 1 functions

- **CVehicleHullAI_MoveOutside**: 1 functions

- **CVehicleHullAI_MoveOutside_1**: 1 functions

- **CVehicleHullAI_LiesInside**: 1 functions

- **cxx_global_array_dtor_4453**: 1 functions

- **CTaskVehicleGun_NeedsToSmashWindowFromTargetPos**: 1 functions

- **CTaskMountThrowProjectile_RestartMoveNetwork**: 1 functions

- **CTaskMountThrowProjectile_CheckForDrop**: 1 functions

- **CTaskVehicleGun_ClearOutPartialSmashedWindow**: 1 functions

- **CTaskMountThrowProjectile_ThrowProjectileImmediately**: 1 functions

- **CTaskMountThrowProjectile_CreateQueriableState**: 1 functions

- **CTaskMountThrowProjectile_ReadQueriableState**: 1 functions

- **CTaskMountThrowProjectile_ShouldBlockHandIk**: 1 functions

- **CClonedMountThrowProjectileInfo_CreateCloneFSMTask**: 1 functions

- **cxx_global_array_dtor_4554**: 1 functions

- **CTaskRideTrain_CTaskRideTrain**: 1 functions

- **CTaskRideTrain_CTaskRideTrain_1**: 1 functions

- **CTaskRideTrain_CTaskRideTrain_123444**: 1 functions

- **CTaskRideTrain_DoAbort**: 1 functions

- **CTaskTrainBase_CTaskTrainBase**: 1 functions

- **CTaskRideTrain_ShouldAbort**: 1 functions

- **cxx_global_array_dtor_4563**: 1 functions

- **CTaskTrainBase_CTaskTrainBase_1**: 1 functions

- **CTaskTrainBase_CTaskTrainBase_2**: 1 functions

- **CTaskTrainBase_CreateNavTask**: 1 functions

- **CTaskTrainBase**: 1 functions

- **CTaskGetOnTrain_CTaskGetOnTrain**: 1 functions

- **CTaskGetOnTrain**: 1 functions

- **CTaskGetOffTrain**: 1 functions

- **cxx_global_array_dtor_4567**: 1 functions

- **CTaskTryToGrabVehicleDoor_CTaskTryToGrabVehicleDoor_1**: 1 functions

- **CTaskTryToGrabVehicleDoor_CTaskTryToGrabVehicleDoor_123479**: 1 functions

- **cxx_global_array_dtor_4573**: 1 functions

- **CTaskVehicleFSM_ShouldClipSetBeStreamedOut**: 1 functions

- **CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug**: 1 functions

- **CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug_1**: 1 functions

- **CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug_123502**: 1 functions

- **CTaskAttachedVehicleAnimDebug_Align_OnUpdate**: 1 functions

- **CTaskAttachedVehicleAnimDebug_OpenDoor_OnEnter**: 1 functions

- **CTaskAttachedVehicleAnimDebug_OpenDoor_OnUpdate**: 1 functions

- **CTaskAttachedVehicleAnimDebug_CloseDoorFromInside_OnUpdate**: 1 functions

- **CTaskAttachedVehicleAnimDebug_CloseDoorFromOutside_OnEnter**: 1 functions

- **CTaskAttachedVehicleAnimDebug_AttachPedForState**: 1 functions

- **CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon**: 1 functions

- **CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon_1**: 1 functions

- **CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon_123558**: 1 functions

- **CTaskVehicleMountedWeapon_StreamingClips_OnUpdate**: 1 functions

- **CTaskVehicleMountedWeapon_Idle_OnEnter**: 1 functions

- **CTaskVehicleMountedWeapon_Idle_OnUpdate**: 1 functions

- **CTaskVehicleMountedWeapon_WantsToFire**: 1 functions

- **CTaskVehicleMountedWeapon_CanFireAtTarget**: 1 functions

- **CTaskVehicleMountedWeapon_ShouldPreventAimingOrFiringDueToLookBehind**: 1 functions

- **CTaskVehicleMountedWeapon_EvaluateTerrainForFireDirection**: 1 functions

- **CTaskVehicleMountedWeapon_WantsToAim**: 1 functions

- **CTaskVehicleMountedWeapon_DoTerrainProbe**: 1 functions

- **CTaskVehicleMountedWeapon_CreateQueriableState**: 1 functions

- **CTaskVehicleMountedWeapon_ReadQueriableState**: 1 functions

- **CTaskVehicleMountedWeapon_CreateTaskForClonePed**: 1 functions

- **CClonedControlTaskVehicleMountedWeaponInfo_CClonedControlTaskVehicleMountedWeaponInfo**: 1 functions

- **CClonedControlTaskVehicleMountedWeaponInfo_CClonedControlTaskVehicleMountedWeaponInfo_123596**: 1 functions

- **CClonedControlTaskVehicleMountedWeaponInfo_CreateCloneFSMTask**: 1 functions

- **CClonedVehicleGunInfo_CreateCloneFSMTask**: 1 functions

- **CTaskVehicleGun_CTaskVehicleGun_1**: 1 functions

- **CTaskVehicleGun_CTaskVehicleGun_123601**: 1 functions

- **CTaskVehicleGun_SmashWindow_OnEnter**: 1 functions

- **CTaskVehicleGun_WaitingToFire_OnUpdate**: 1 functions

- **CTaskVehicleGun_Gun_OnEnter**: 1 functions

- **CTaskVehicleGun_Gun_OnUpdate**: 1 functions

- **CTaskVehicleGun_SelectClipSet**: 1 functions

- **CTaskVehicleGun_CheckFiringConditions**: 1 functions

- **CTaskVehicleGun_CreateQueriableState**: 1 functions

- **CTaskVehicleGun_ReadQueriableState**: 1 functions

- **CTaskVehicleProjectile_CTaskVehicleProjectile**: 1 functions

- **CTaskVehicleProjectile_CreateQueriableState**: 1 functions

- **CTaskVehicleProjectile_ReadQueriableState**: 1 functions

- **CSimpleBlendHelper**: 1 functions

- **CTaskVehicleProjectile_ThrowProjectileImmediately**: 1 functions

- **CClonedVehicleProjectileInfo_CreateCloneFSMTask**: 1 functions

- **cxx_global_array_dtor_5037**: 1 functions

- **CTaskMotionInVehicle_CheckForStill**: 1 functions

- **CTaskMotionInVehicle_CheckForMovingForwards**: 1 functions

- **CTaskMotionInVehicle_CheckForShunt**: 1 functions

- **CTaskMotionInVehicle_CheckForReverse**: 1 functions

- **CTaskMotionInVehicle_CheckForStartingEngine**: 1 functions

- **CTaskMotionInVehicle_CheckForHotwiring**: 1 functions

- **GetSteeringLerpScale**: 1 functions

- **CTaskMotionInVehicle_CTaskMotionInVehicle**: 1 functions

- **CTaskMotionInVehicle_CTaskMotionInVehicle_1**: 1 functions

- **CTaskMotionInVehicle_CTaskMotionInVehicle_123666**: 1 functions

- **CTaskMotionInVehicle_CheckCanPedMoveToDriversSeat**: 1 functions

- **CTaskMotionInAutomobile_CTaskMotionInAutomobile**: 1 functions

- **CTaskMotionOnBicycle_CTaskMotionOnBicycle**: 1 functions

- **CTaskMotionInVehicle_OnBicycle_OnUpdate**: 1 functions

- **CTaskMotionInAutomobile_CheckIfVehicleIsDoingBurnout**: 1 functions

- **CTaskMotionInVehicle_CreatePlayerControlTask**: 1 functions

- **cxx_global_array_dtor_5338**: 1 functions

- **CTaskMotionInAutomobile_WillAbortPuttingOnHelmet**: 1 functions

- **CTaskMotionInAutomobile_CTaskMotionInAutomobile_1**: 1 functions

- **CBikeLeanAngleHelper_CBikeLeanAngleHelper**: 1 functions

- **CTaskMotionInAutomobile_CTaskMotionInAutomobile_123694**: 1 functions

- **CTaskMotionInAutomobile_CanUsePoVAnims**: 1 functions

- **CTaskMotionInAutomobile_CheckForShuntFromHighFall**: 1 functions

- **CTaskMotionInAutomobile_ShouldUseLowriderLeanAltClipset**: 1 functions

- **CTaskMotionInAutomobile_ShouldUseBaseIdle**: 1 functions

- **CTaskMotionInAutomobile_CheckForHelmetVisorSwitch**: 1 functions

- **CTaskMotionInAutomobile_StartMoveNetwork**: 1 functions

- **CTaskMotionInAutomobile_CheckForStartingEngine**: 1 functions

- **CTaskMotionInAutomobile_CheckForChangingStation**: 1 functions

- **CTaskMotionInAutomobile_ShouldUseSitToStillTransition**: 1 functions

- **CTaskMotionInAutomobile_CheckIfPedWantsToMove**: 1 functions

- **CTaskMotionInAutomobile_ShouldPanic**: 1 functions

- **CTaskMotionInAutomobile_CheckForHorn**: 1 functions

- **CTaskMotionInAutomobile_PickRoadRageAnim**: 1 functions

- **CTaskMotionInAutomobile_ShouldUseLowriderLean**: 1 functions

- **CTaskMotionInAutomobile_ShouldBeAgitated**: 1 functions

- **CTaskMotionInAutomobile_CanTransitionToFirstPersonAnims**: 1 functions

- **CTaskMotionInAutomobile_CanBeDucked**: 1 functions

- **CTaskMotionInAutomobile_PlayerShouldBeAgitated**: 1 functions

- **cxx_global_array_dtor_5698**: 1 functions

- **CTaskMotionOnBicycle_CheckForWantsToMove**: 1 functions

- **CTaskMotionOnBicycle_WantsToDoSpecialMove**: 1 functions

- **CTaskMotionOnBicycle_WantsToTrackStand**: 1 functions

- **CTaskMotionOnBicycle_CheckForStill**: 1 functions

- **CTaskMotionOnBicycle_CanTransitionToStill**: 1 functions

- **CTaskMotionOnBicycle_PedWantsToStand**: 1 functions

- **CTaskMotionOnBicycle_CTaskMotionOnBicycle_1**: 1 functions

- **CTaskMotionOnBicycle_CTaskMotionOnBicycle_123834**: 1 functions

- **CTaskMotionOnBicycle_AreMoveNetworkStatesValid**: 1 functions

- **CTaskMotionOnBicycle_CheckForRestartingStateDueToCameraSwitch**: 1 functions

- **CTaskMotionOnBicycle_CheckForReversingTransition**: 1 functions

- **CTaskMotionOnBicycle_CheckForStandingTransition**: 1 functions

- **CTaskMotionOnBicycleController_CTaskMotionOnBicycleController**: 1 functions

- **CTaskMotionOnBicycle_CheckForImpactTransition**: 1 functions

- **CTaskMotionOnBicycle_ShouldChangeAnimsDueToCameraSwitch**: 1 functions

- **CTaskMotionOnBicycle_VisualizeClip**: 1 functions

- **CTaskMotionOnBicycle_VisualizePrepLaunchTags**: 1 functions

- **CTaskMotionOnBicycle_VisualizeTrackStandTags**: 1 functions

- **cxx_global_array_dtor_5798**: 1 functions

- **CTaskMotionOnBicycleController_CTaskMotionOnBicycleController_1**: 1 functions

- **CTaskMotionOnBicycleController_CTaskMotionOnBicycleController_123897**: 1 functions


## Per-function semantic index

### CTaskVehicleFSM_GetGenericClipBlendParams (lines 5001192–5001237, 47 lines)

query / predicate; calls CTaskVehicleFSM_GetGenericClipBlendParams, CMoveNetworkHelper_GetFloat, rage_atArray_float_0_Grow, CMoveNetworkHelper_GetClip, rage_atArray_rage_restService_0_Grow; 1 loop(s)

### CTaskVehicleFSM_ComputeRemainingAnimTransform (lines 5001239–5001999, 762 lines)

calculation (math/geometry/route); calls CTaskVehicleFSM_ComputeRemainingAnimTransform, rage_fwAnimHelpers_GetMoverTrackTranslationDiff, rage_fwAnimHelpers_GetMoverTrackRotation, f32x4_mul, SimdShuffleOp, f32x4_sub...; globals 25448928, 8350384, 7736718, 11547139...; 1 loop(s); 2 atomic op(s)

### CTaskVehicleFSM_TransformRelativeOffsetsToWorldSpace (lines 5002001–5002065, 66 lines)

helper; calls CTaskVehicleFSM_TransformRelativeOffsetsToWorldSpace, SimdShuffleOp, f32x4_mul, f32x4_add, f32x4_sub, v128_bitselect...

### CTaskExitVehicleSeat_GetGroundFixupHeight (lines 5002067–5002078, 13 lines)

query / predicate; calls CTaskExitVehicleSeat_GetGroundFixupHeight; globals 25445500

### CTaskVehicleFSM_ApplyGroundAndOrientationFixup (lines 5002080–5002262, 184 lines)

helper; calls CTaskVehicleFSM_ApplyGroundAndOrientationFixup, i32x4_bitmask, f32x4_abs, SimdShuffleOp, f32x4_mul, f32x4_sub...

### CTaskVehicleFSM_ApplyMoverFixup (lines 5002264–5002768, 506 lines)

helper; calls CTaskVehicleFSM_ApplyMoverFixup, rage_bkManager_FindBank, rage_bkManager_IsBankThread, rage_bkGroup_AddToggle_1, CDebugScene_QueueTuneWidget, CDebugScene_TuneWidgetData_TuneWidgetData...; globals 25448940, 8350384, 25448936, 10852368...; 5 atomic op(s)

### CTaskExitVehicleSeat_UpdateTarget (lines 5002770–5003086, 318 lines)

updates target position/state; calls CTaskExitVehicleSeat_UpdateTarget, CMoveNetworkHelper_GetClip, CVehicle_GetEntryAnimInfo, CPed_IsFirstPersonShooterModeEnabledForPlayer, rage_aiTaskTree_FindTaskByTypeActive, CTaskVehicleFSM_ComputeTargetTransformInWorldSpace...; globals 19623284, 19622644, 19624516, 19621012...

### CTaskExitVehicleSeat_ProcessMoveSignals (lines 5003088–5003130, 44 lines)

processing / event handling; calls CTaskExitVehicleSeat_ProcessMoveSignals, CMoveNetworkHelperFunctions_IsMoveNetworkStateFinished, CPedAILodManager_ShouldDoFullUpdate, CTaskExitVehicleSeat_SendMoveSignalsForExitToAim, CMoveNetworkHelper_GetBoolean

### CTaskExitVehicleSeat_Debug (lines 5003132–5003146, 16 lines)

debug / diagnostics; calls CTaskExitVehicleSeat_Debug, rage_Matrix34_FromQuaternion, rage_grcDebugDraw_Axis

### CTaskCloseVehicleDoorFromOutside_CTaskCloseVehicleDoorFromOutside_1 (lines 5003148–5003186, 40 lines)

constructor / variant; calls CTaskCloseVehicleDoorFromOutside_CTaskCloseVehicleDoorFromOutside_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip, rage_aiTask_aiTask_1; globals 12321880; 2 vtable call(s); 1 loop(s); 2 atomic op(s)

### CTaskCloseVehicleDoorFromOutside_CTaskCloseVehicleDoorFromOutside_123298 (lines 5003188–5003192, 6 lines)

helper; calls CTaskCloseVehicleDoorFromOutside_CTaskCloseVehicleDoorFromOutside_123298, CTaskCloseVehicleDoorFromOutside_CTaskCloseVehicleDoorFromOutside_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskCloseVehicleDoorFromOutside_CleanUp (lines 5003194–5003197, 5 lines)

cleanup / shutdown; calls CTaskCloseVehicleDoorFromOutside_CleanUp; 1 vtable call(s)

### CTaskCloseVehicleDoorFromOutside_ProcessPreFSM (lines 5003199–5003210, 13 lines)

pre-FSM setup / signal processing; calls CTaskCloseVehicleDoorFromOutside_ProcessPreFSM

### CTaskCloseVehicleDoorFromOutside_UpdateFSM (lines 5003212–5003675, 465 lines)

FSM state-machine update (per-frame behavior); calls CTaskCloseVehicleDoorFromOutside_UpdateFSM, CVehicle_GetEntryExitPoint, CTaskClimbLadder_SetTaskState, CModelSeatInfo_GetBoneIndexFromEntryPoint, CVehicle_GetDoorFromBoneIndex, rage_bkManager_FindBank...; globals 25446556, 8350384, 7736368, 25446548...; 7 vtable call(s); 2 loop(s); 1 atomic op(s)

### CTaskCloseVehicleDoorFromOutside_ProcessMoveSignals (lines 5003677–5003691, 16 lines)

processing / event handling; calls CTaskCloseVehicleDoorFromOutside_ProcessMoveSignals, CMoveNetworkHelperFunctions_IsMoveNetworkStateFinished

### CTaskCloseVehicleDoorFromOutside_Debug (lines 5003693–5003710, 19 lines)

debug / diagnostics; calls CTaskCloseVehicleDoorFromOutside_Debug, CModelSeatInfo_GetBoneIndexFromEntryPoint, CVehicle_GetDoorFromBoneIndex, f64_promote_f32, rage_grcDebugDraw_AddDebugOutput_1

### CTaskReactToBeingJacked_CTaskReactToBeingJacked (lines 5003712–5003759, 49 lines)

helper; calls CTaskReactToBeingJacked_CTaskReactToBeingJacked, rage_aiTask_aiTask, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_New, rage_sysCriticalSectionToken_Unlock, rage_fwKnownRefHolder_fwKnownRefHolder; globals 15567136, 10854468, 10854472, 12321880

### CTaskReactToBeingJacked_CTaskReactToBeingJacked_1 (lines 5003761–5003836, 77 lines)

constructor / variant; calls CTaskReactToBeingJacked_CTaskReactToBeingJacked_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip, rage_aiTask_aiTask_1; globals 12321880; 2 vtable call(s); 3 loop(s); 2 atomic op(s)

### CTaskReactToBeingJacked_CTaskReactToBeingJacked_123312 (lines 5003838–5003841, 5 lines)

helper; calls CTaskReactToBeingJacked_CTaskReactToBeingJacked_123312, CTaskReactToBeingJacked_CTaskReactToBeingJacked_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskReactToBeingJacked_ProcessPreFSM (lines 5003843–5003864, 23 lines)

pre-FSM setup / signal processing; calls CTaskReactToBeingJacked_ProcessPreFSM, CPedIntelligence_IsFriendlyWith, CIkManager_LookAt

### CTaskReactToBeingJacked_UpdateFSM (lines 5003866–5004306, 442 lines)

FSM state-machine update (per-frame behavior); calls CTaskReactToBeingJacked_UpdateFSM, CPedIntelligence_IsFriendlyWith, rage_fwRegdRef_rage_fwEntity_rage_fwRefAwareBase_Reset, CSeatManager_CountPedsInSeats, i32_wrap_i64, rage_aiTaskTree_FindTaskByTypeActive...; globals 28501281, 25408152; 2 vtable call(s); 1 loop(s)

### CTaskReactToBeingJacked_HasJackStarted (lines 5004308–5004336, 30 lines)

query / predicate; calls CTaskReactToBeingJacked_HasJackStarted, rage_aiTaskTree_FindTaskByTypeActive

### cxx_global_array_dtor_4360 (lines 5004338–5004340, 4 lines)

cleanup / shutdown; calls cxx_global_array_dtor_4360, CTuning_CTuning

### CTaskReactToBeingAskedToLeaveVehicle_CTaskReactToBeingAskedToLeaveVehicle_1 (lines 5004342–5004399, 59 lines)

constructor / variant; calls CTaskReactToBeingAskedToLeaveVehicle_CTaskReactToBeingAskedToLeaveVehicle_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip, rage_aiTask_aiTask_1; globals 12321880; 2 vtable call(s); 2 loop(s); 2 atomic op(s)

### CTaskReactToBeingAskedToLeaveVehicle_CTaskReactToBeingAskedToLeaveVehicle_123325 (lines 5004401–5004406, 7 lines)

helper; calls CTaskReactToBeingAskedToLeaveVehicle_CTaskReactToBeingAskedToLeaveVehicle_123325, CTaskReactToBeingAskedToLeaveVehicle_CTaskReactToBeingAskedToLeaveVehicle_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskReactToBeingAskedToLeaveVehicle_UpdateFSM (lines 5004408–5004539, 133 lines)

FSM state-machine update (per-frame behavior); calls CTaskReactToBeingAskedToLeaveVehicle_UpdateFSM, rage_aiTask_SetState, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, CAITarget_CAITarget_1, rage_aiTask_aiTask...; globals 25408152, 15567136, 10854468, 10854472...; 1 loop(s)

### CTaskGoToCarDoorAndStandStill_CTaskGoToCarDoorAndStandStill_1 (lines 5004541–5004598, 59 lines)

constructor / variant; calls CTaskGoToCarDoorAndStandStill_CTaskGoToCarDoorAndStandStill_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip, rage_aiTask_aiTask_1; globals 12321880; 2 vtable call(s); 2 loop(s); 2 atomic op(s)

### CTaskGoToCarDoorAndStandStill_CTaskGoToCarDoorAndStandStill_123332 (lines 5004600–5004603, 5 lines)

helper; calls CTaskGoToCarDoorAndStandStill_CTaskGoToCarDoorAndStandStill_123332, CTaskGoToCarDoorAndStandStill_CTaskGoToCarDoorAndStandStill_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskGoToCarDoorAndStandStill_UpdateFSM (lines 5004605–5004797, 194 lines)

FSM state-machine update (per-frame behavior); calls CTaskGoToCarDoorAndStandStill_UpdateFSM, CTaskEnterVehicle_CalculateLocalSpaceEntryModifier, rage_aiTask_SetState, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor...; globals 25408152, 15562208, 12321880; 1 vtable call(s); 1 loop(s)

### CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor (lines 5004799–5004869, 72 lines)

helper; calls CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor, rage_aiTask_aiTask, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_New, rage_sysCriticalSectionToken_Unlock, rage_fwKnownRefHolder_fwKnownRefHolder; globals 15567136, 10854468, 10854472, 10852368...

### CTaskMoveGoToVehicleDoor_HasAchievedDoor (lines 5004871–5004908, 39 lines)

query / predicate; calls CTaskMoveGoToVehicleDoor_HasAchievedDoor, CTaskEnterVehicle_PassesPlayerDriverAlignCondition, CTaskEnterVehicleAlign_PassesGroundConditionForAlign, CTaskMoveGoToVehicleDoor_CalcTargetPositions, SimdLaneOp, CTaskMoveGoToVehicleDoor_ComputeTargetRadius; globals 25443684

### CTaskMoveGoToVehicleDoor_CalcTargetPositions (lines 5004910–5005022, 114 lines)

calculation (math/geometry/route); calls CTaskMoveGoToVehicleDoor_CalcTargetPositions, CEntryExitPoint_GetEntryPointPosition, CTaskEnterVehicle_CalculateLocalSpaceEntryModifier, SimdLaneOp, SimdStoreLane, f32x4_add...; globals 10852368, 10852372, 10852376, 25407612...

### CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_1 (lines 5005024–5005065, 43 lines)

constructor / variant; calls CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_1, rage_fwBasePool_Delete, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip...; globals 15545576, 12321880; 2 vtable call(s); 1 loop(s); 2 atomic op(s)

### non_virtual_thunk_to_CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor (lines 5005067–5005069, 4 lines)

helper; calls non_virtual_thunk_to_CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor, CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_1

### CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_123344 (lines 5005071–5005074, 5 lines)

helper; calls CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_123344, CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### non_virtual_thunk_to_CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_123345 (lines 5005076–5005079, 5 lines)

helper; calls non_virtual_thunk_to_CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_123345, CTaskMoveGoToVehicleDoor_CTaskMoveGoToVehicleDoor_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskMoveGoToVehicleDoor_Debug (lines 5005081–5005115, 36 lines)

debug / diagnostics; calls CTaskMoveGoToVehicleDoor_Debug, rage_grcDebugDraw_Line_2, rage_grcDebugDraw_Line_3, rage_grcDebugDraw_Sphere; globals 25446612, 12321260; 1 vtable call(s); 1 loop(s)

### CTaskMoveGoToVehicleDoor_AdjustPosForVehicleSpeed (lines 5005117–5005218, 103 lines)

helper; calls CTaskMoveGoToVehicleDoor_AdjustPosForVehicleSpeed, SimdLaneOp, CPed_GetCurrentMotionTask, modff, i64_extend_i32_s, i32_trunc_sat_f32_s...; globals 5240096, 5240820; 3 vtable call(s); 1 loop(s)

### CTaskMoveGoToVehicleDoor_ProcessPreFSM (lines 5005220–5005225, 7 lines)

pre-FSM setup / signal processing; calls CTaskMoveGoToVehicleDoor_ProcessPreFSM

### CTaskMoveGoToVehicleDoor_ChooseGoToDoorMBR (lines 5007352–5007458, 108 lines)

helper; calls CTaskMoveGoToVehicleDoor_ChooseGoToDoorMBR, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider_2, rage_bkBank_UnSetCurrentGroup...; globals 25446680, 8350384, 25446684, 5239416...; 1 vtable call(s); 2 atomic op(s)

### CTaskMoveGoToVehicleDoor_WarpIfPossible (lines 5007460–5007487, 29 lines)

helper; calls CTaskMoveGoToVehicleDoor_WarpIfPossible, rage_aiTaskTree_FindTaskByTypeActive, CTaskEnterVehicle_WarpIfPossible

### CTaskMoveGoToVehicleDoor_IsAlreadyInPositionToEnter (lines 5007489–5007533, 46 lines)

query / predicate; calls CTaskMoveGoToVehicleDoor_IsAlreadyInPositionToEnter, CVehicle_GetBoardingPoints, CEntryExitPoint_GetEntryPointPosition, SimdLaneOp

### CTaskMoveGoToVehicleDoor_HasCarMoved (lines 5007535–5007577, 44 lines)

query / predicate; calls CTaskMoveGoToVehicleDoor_HasCarMoved; globals 7736376, 25446584; 1 loop(s)

### CVehicleHullCalculator_CalculateHullForVehicle (lines 5007579–5008272, 695 lines)

calculation (math/geometry/route); calls CVehicleHullCalculator_CalculateHullForVehicle, i32_wrap_i64, i64_extend_i32_s, CVehicleVariationInstance_GetKit, i32x4_splat, v128_any_true...; globals 7738108, 7738112, 25456920, 25456912...; 2 vtable call(s); 14 loop(s)

### CVehicleHullAI_MoveOutside (lines 5008274–5008308, 36 lines)

helper; calls CVehicleHullAI_MoveOutside, SimdStoreLane, LoadZero, rage_geom2D_Test2DSegVsSeg, f32x4_add, LoadSplat...; 1 loop(s)

### CVehicleHullAI_MoveOutside_1 (lines 5008310–5008356, 48 lines)

constructor / variant; calls CVehicleHullAI_MoveOutside_1; 1 loop(s)

### CVehicleHullAI_CalcShortestRouteToTarget (lines 5008358–5008903, 547 lines)

calculation (math/geometry/route); calls CVehicleHullAI_CalcShortestRouteToTarget, rage_geomTValues_FindTValueSegToPoint, i32_wrap_i64, i64_extend_i32_s, CVehicleHullAI_TestIsRouteClear, CVehicleHullAI_MoveOutside_1...; 16 loop(s)

### CVehicleHullAI_LiesInside (lines 5008905–5008935, 32 lines)

helper; calls CVehicleHullAI_LiesInside; 1 loop(s)

### CTaskMoveGoToVehicleDoor_TestIsSegmentClear (lines 5008937–5009247, 312 lines)

query / predicate; calls CTaskMoveGoToVehicleDoor_TestIsSegmentClear, i32_trunc_sat_f32_s, WorldProbe_CShapeTestDesc_SetIncludeEntity, WorldProbe_CShapeTestDesc_SetResultsStructure, WorldProbe_CShapeTestManager_DebugSubmitTest, WorldProbe_CShapeTestManager_AbortTest...; globals 10852380, 15406232; 3 vtable call(s); 3 loop(s)

### CVehicleHullAI_Init (lines 5009249–5009253, 6 lines)

initialization; calls CVehicleHullAI_Init, CVehicleHullCalculator_CalculateHullForVehicle; globals 25456920, 25456912

### CVehicleHullAI_TestIsRouteClear (lines 5009255–5009633, 380 lines)

query / predicate; calls CVehicleHullAI_TestIsRouteClear, WorldProbe_CShapeTestDesc_SetExcludeEntity, WorldProbe_CShapeTestDesc_SetResultsStructure, cxa_guard_acquire, cxa_guard_release, i32_trunc_sat_f32_s...; globals 10852380, 10852376, 10852372, 10852368...; 4 vtable call(s); 4 loop(s); 1 atomic op(s)

### cxx_global_array_dtor_4453 (lines 5009635–5009646, 13 lines)

cleanup / shutdown; calls cxx_global_array_dtor_4453, rage_vfxBrokenFragInfo_vfxBrokenFragInfo

### CTaskMountThrowProjectile_FindMeleeNetworkDamageForHitPed (lines 5009648–5009700, 54 lines)

helper; calls CTaskMountThrowProjectile_FindMeleeNetworkDamageForHitPed; globals 25446848, 25446856, 25446904, 25446928...

### CTaskMountThrowProjectile_GetOverriddenGameplayCameraSettings (lines 5009702–5009750, 50 lines)

query / predicate; calls CTaskMountThrowProjectile_GetOverriddenGameplayCameraSettings, ReportPlayerResetMismatch, CPlayerSwitchInterface_IsActive, CPed_GetControlFromPlayer, i32_wrap_i64, rage_ioValue_IsDown...; globals 23319120, 12839924, 4334632; 1 loop(s)

### CTaskMountThrowProjectile_ProcessPreFSM (lines 5009752–5010037, 287 lines)

pre-FSM setup / signal processing; calls CTaskMountThrowProjectile_ProcessPreFSM, CMoveNetworkHelper_GetBoolean, CPed_GetControlFromPlayer, CControl_GetInputName, rage_diagLogf2, CControl_DebugOutputScriptCallStack...; globals 24035147, 4334628, 12839924; 4 loop(s)

### CTaskMountThrowProjectile_UpdateTarget (lines 5010039–5010059, 22 lines)

updates target position/state; calls CTaskMountThrowProjectile_UpdateTarget, CAITarget_SetPosition, CWeaponTarget_Update, CAITarget_GetIsValid, CWeaponTarget_GetPositionWithFiringOffsets

### CTaskMountThrowProjectile_IsStateValidForFPSIK (lines 5010061–5010086, 27 lines)

query / predicate; calls CTaskMountThrowProjectile_IsStateValidForFPSIK, CPed_IsInFirstPersonVehicleCamera, CPed_IsFirstPersonShooterModeEnabledForPlayer, CTaskMotionPed_GetWeaponInfo

### CTaskVehicleGun_NeedsToSmashWindowFromTargetPos (lines 5014048–5014160, 114 lines)

helper; calls CTaskVehicleGun_NeedsToSmashWindowFromTargetPos, CPed_IsInFirstPersonVehicleCamera, CPedWeaponManager_GetIsArmedMelee, CTaskSmashCarWindow_GetWindowToSmash, rage_aiTaskTree_FindTaskByTypeActive, CTaskVehicleGun_GetDoorForPed...; globals 25459820, 19624340, 19275176, 19239148; 1 vtable call(s)

### CTaskMountThrowProjectile_RestartMoveNetwork (lines 5014162–5014485, 325 lines)

helper; calls CTaskMountThrowProjectile_RestartMoveNetwork, rage_fwAnimDirector_GetNetworkDef, rage_fwAnimDirector_CreateNetworkPlayer, rage_mvParameterBuffer_GenerateFreeCapacity, i64_extend_i32_s, i32_wrap_i64...; globals 15568352, 25446692, 25446820, 25459780...; 3 vtable call(s); 8 loop(s)

### CTaskMountThrowProjectile_UpdateFPSMoVESignals (lines 5014487–5014667, 182 lines)

helper; calls CTaskMountThrowProjectile_UpdateFPSMoVESignals, cxa_guard_acquire, rage_atHashStringNamespaceSupport_AddString, cxa_guard_release, rage_fwClipSetManager_GetClip, CMoveNetworkHelper_SetClip...; globals 25447720, 25447736, 10854472, 25447752...; 11 atomic op(s)

### CTaskMountThrowProjectile_CheckForDrop (lines 5014669–5014796, 129 lines)

helper; calls CTaskMountThrowProjectile_CheckForDrop, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25448032, 8350384, 25448028, 25448036...; 1 vtable call(s); 2 atomic op(s)

### CTaskMountThrowProjectile_UpdateAiming (lines 5014798–5015117, 321 lines)

helper; calls CTaskMountThrowProjectile_UpdateAiming, CPedWeaponManager_GetEquippedWeapon, CPed_GetControlFromPlayer, i32_wrap_i64, rage_ioValue_IsUp, camInterface_GetPlayerControlCamAimFrame...; globals 20159720, 12839924, 4334632, 19235056...; 2 vtable call(s)

### CTaskMountThrowProjectile_SetNextStateFromNetwork (lines 5015119–5015194, 77 lines)

setter; calls CTaskMountThrowProjectile_SetNextStateFromNetwork, rage_aiTask_SetState; globals 12321264

### CTaskMountThrowProjectile_GetIsBikeMoving (lines 5015196–5015235, 41 lines)

query / predicate; calls CTaskMountThrowProjectile_GetIsBikeMoving, CHandlingData_GetHandlingData; 1 vtable call(s)

### CTaskVehicleGun_ClearOutPartialSmashedWindow (lines 5015237–5015268, 33 lines)

helper; calls CTaskVehicleGun_ClearOutPartialSmashedWindow, CTaskVehicleGun_NeedsToSmashWindowFromTargetPos, CSeatManager_GetPedsSeatIndex, CModelSeatInfo_GetEntryPointIndexForSeat, CVehicleEntryPointInfo_GetWindowId, CVehicleModelInfo_GetEntryPointInfo...; globals 23389596, 6143456; 1 vtable call(s)

### CTaskMountThrowProjectile_ThrowProjectileImmediately (lines 5015270–5015488, 220 lines)

helper; calls CTaskMountThrowProjectile_ThrowProjectileImmediately, CProjectileManager_FireOrPlacePendingProjectile, CPedWeaponManager_DestroyEquippedWeaponObject, CPedWeaponManager_GetEquippedWeapon, rage_crSkeletonData_ConvertBoneIdToIndex, SimdStoreLane...; globals 12321248; 4 vtable call(s)

### CTaskMountThrowProjectile_CreateQueriableState (lines 5015490–5015527, 39 lines)

helper; calls CTaskMountThrowProjectile_CreateQueriableState, rage_sysMemPoolAllocator_Allocate, Quitf_1, CTaskInfo_CTaskInfo, CAITarget_CAITarget_4; globals 20217488; 1 vtable call(s)

### CTaskMountThrowProjectile_ReadQueriableState (lines 5015529–5015542, 15 lines)

helper; calls CTaskMountThrowProjectile_ReadQueriableState; 2 vtable call(s)

### CTaskMountThrowProjectile_UpdateClonedFSM (lines 5015544–5015563, 21 lines)

helper; calls CTaskMountThrowProjectile_UpdateClonedFSM, CTaskMountThrowProjectile_SetNextStateFromNetwork; 1 vtable call(s)

### CTaskMountThrowProjectile_IsInScope (lines 5015565–5015574, 11 lines)

query / predicate; calls CTaskMountThrowProjectile_IsInScope, CTaskFSMClone_IsInScope

### CTaskMountThrowProjectile_ProcessCachedNetworkDamage (lines 5015576–5015675, 101 lines)

processing / event handling; calls CTaskMountThrowProjectile_ProcessCachedNetworkDamage, CWeapon_ReceiveFireMessage, SimdLaneOp, audPedAudioEntity_PlayBikeMeleeCombatHit, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete...; globals 15406232, 12321880; 3 loop(s)

### CTaskMountThrowProjectile_ProcessPostCamera (lines 5015677–5016122, 447 lines)

processing / event handling; calls CTaskMountThrowProjectile_ProcessPostCamera, CTaskMountThrowProjectile_IsStateValidForFPSIK, CPed_IsInFirstPersonVehicleCamera, operator_delete, CFirstPersonIkHelper_CFirstPersonIkHelper_1, operator_new...; globals 25317520, 25447944, 8350384, 25447948...; 13 atomic op(s)

### CTaskMountThrowProjectile_ProcessPostPreRender (lines 5016124–5016146, 24 lines)

processing / event handling; calls CTaskMountThrowProjectile_ProcessPostPreRender, CTaskMountThrowProjectile_GetIsCloneInDamageWindow, CTaskMountThrowProjectile_ProcessCachedNetworkDamage, CTaskMountThrowProjectile_UpdateAiming; 1 vtable call(s)

### CTaskMountThrowProjectile_GetIsCloneInDamageWindow (lines 5016148–5016188, 42 lines)

query / predicate; calls CTaskMountThrowProjectile_GetIsCloneInDamageWindow, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider_2, rage_bkBank_UnSetCurrentGroup...; globals 25448056, 8350384, 7736568; 1 atomic op(s)

### CTaskMountThrowProjectile_CleanUp (lines 5016190–5016265, 77 lines)

cleanup / shutdown; calls CTaskMountThrowProjectile_CleanUp, CPedWeaponManager_DestroyEquippedWeaponObject, CTaskMountThrowProjectile_ProcessCachedNetworkDamage, CMovePed_ClearTaskNetwork, rage_fwAnimDirector_GetMove, CMovePed_ClearSecondaryTaskNetwork...; globals 25446824

### CTaskVehicleGun_GetDoorForPed (lines 5016267–5016288, 23 lines)

query / predicate; calls CTaskVehicleGun_GetDoorForPed, CSeatManager_GetPedsSeatIndex, CVehicle_IsEntryIndexValid, CModelSeatInfo_GetEntryPointIndexForSeat, CModelSeatInfo_GetBoneIndexFromEntryPoint, CVehicle_GetDoorFromBoneIndex

### CTaskMountThrowProjectile_ShouldBlockHandIk (lines 5016290–5016330, 42 lines)

helper; calls CTaskMountThrowProjectile_ShouldBlockHandIk, CPed_IsInFirstPersonVehicleCamera, CPed_IsFirstPersonShooterModeEnabledForPlayer, CMoveNetworkHelper_GetFloat; 1 vtable call(s)

### CClonedMountThrowProjectileInfo_CreateCloneFSMTask (lines 5016332–5016386, 56 lines)

helper; calls CClonedMountThrowProjectileInfo_CreateCloneFSMTask, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, SimdLoadLane, CTaskAimGun_CTaskAimGun_1, rage_fwClipSetRequestHelper_fwClipSetRequestHelper_1...; globals 25408152

### cxx_global_array_dtor_4554 (lines 5016388–5016390, 4 lines)

cleanup / shutdown; calls cxx_global_array_dtor_4554, CTuning_CTuning

### CTaskRideTrain_CTaskRideTrain (lines 5016392–5016431, 41 lines)

helper; calls CTaskRideTrain_CTaskRideTrain, rage_aiTask_aiTask, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_New, rage_sysCriticalSectionToken_Unlock, rage_fwKnownRefHolder_fwKnownRefHolder; globals 15567136, 10854468, 10854472, 12321880

### CTaskRideTrain_CTaskRideTrain_1 (lines 5016433–5016494, 63 lines)

constructor / variant; calls CTaskRideTrain_CTaskRideTrain_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip, rage_aiTask_aiTask_1; globals 12321880; 3 vtable call(s); 2 loop(s); 2 atomic op(s)

### CTaskRideTrain_CTaskRideTrain_123444 (lines 5016496–5016499, 5 lines)

helper; calls CTaskRideTrain_CTaskRideTrain_123444, CTaskRideTrain_CTaskRideTrain_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskRideTrain_GetScenarioPoint (lines 5016501–5016505, 6 lines)

query / predicate; calls CTaskRideTrain_GetScenarioPoint; 1 vtable call(s)

### CTaskRideTrain_GetScenarioPointType (lines 5016507–5016511, 6 lines)

query / predicate; calls CTaskRideTrain_GetScenarioPointType; 1 vtable call(s)

### CTaskRideTrain_CleanUp (lines 5016513–5016540, 29 lines)

cleanup / shutdown; calls CTaskRideTrain_CleanUp, i32_wrap_i64, rage_fwRegdRef_rage_fwEntity_rage_fwRefAwareBase_Reset; 1 loop(s)

### CTaskRideTrain_DoAbort (lines 5016542–5016566, 26 lines)

helper; calls CTaskRideTrain_DoAbort, rage_fwRegdRef_rage_fwEntity_rage_fwRefAwareBase_Reset, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, CTaskUseScenario_CTaskUseScenario_1; globals 25408152; 1 vtable call(s)

### CTaskRideTrain_ProcessPreFSM (lines 5016568–5016591, 25 lines)

pre-FSM setup / signal processing; calls CTaskRideTrain_ProcessPreFSM; globals 12321260

### CTaskRideTrain_UpdateFSM (lines 5016593–5016820, 229 lines)

FSM state-machine update (per-frame behavior); calls CTaskRideTrain_UpdateFSM, rage_aiTask_SetState, rage_diagLogf2, i64_extend_i32_s, rage_fwRegdRef_rage_fwEntity_rage_fwRefAwareBase_Reset, CTrain_CanGetOff...; globals 28501183, 25982834, 25982787, 25408152...; 1 vtable call(s); 2 loop(s)

### CTaskTrainBase_CTaskTrainBase (lines 5016822–5016850, 30 lines)

helper; calls CTaskTrainBase_CTaskTrainBase, rage_aiTask_aiTask, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_New, rage_sysCriticalSectionToken_Unlock, rage_fwKnownRefHolder_fwKnownRefHolder; globals 15567136, 10854468, 10854472, 12321880

### CTaskRideTrain_ShouldAbort (lines 5016852–5016874, 24 lines)

helper; calls CTaskRideTrain_ShouldAbort; 3 vtable call(s)

### cxx_global_array_dtor_4563 (lines 5016876–5016878, 4 lines)

cleanup / shutdown; calls cxx_global_array_dtor_4563, CTuning_CTuning

### CTaskTrainBase_CTaskTrainBase_1 (lines 5016880–5016909, 31 lines)

constructor / variant; calls CTaskTrainBase_CTaskTrainBase_1, rage_aiTask_aiTask, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_New, rage_sysCriticalSectionToken_Unlock, rage_fwKnownRefHolder_fwKnownRefHolder; globals 15567136, 10854468, 10854472, 12321880

### CTaskTrainBase_CTaskTrainBase_2 (lines 5016911–5016949, 40 lines)

constructor / variant; calls CTaskTrainBase_CTaskTrainBase_2, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip, rage_aiTask_aiTask_1; globals 12321880; 2 vtable call(s); 1 loop(s); 2 atomic op(s)

### CTaskTrainBase_CreateNavTask (lines 5016951–5016982, 33 lines)

helper; calls CTaskTrainBase_CreateNavTask, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, CTaskMoveFollowNavMesh_CTaskMoveFollowNavMesh_1, CTaskComplexControlMovement_CTaskComplexControlMovement; globals 5239416, 25448156, 25448160, 25408152; 1 vtable call(s)

### CTaskTrainBase_Debug (lines 5016984–5017056, 74 lines)

debug / diagnostics; calls CTaskTrainBase_Debug, SimdLoadLane, LoadZero, f32x4_add, SimdShuffleOp, SimdLaneOp...; 1 vtable call(s)

### CTaskGetOnTrain_CTaskGetOnTrain (lines 5017058–5017061, 5 lines)

query / predicate; calls CTaskGetOnTrain_CTaskGetOnTrain, CTaskTrainBase_CTaskTrainBase_2, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskGetOnTrain_UpdateFSM (lines 5017063–5017228, 167 lines)

FSM state-machine update (per-frame behavior); calls CTaskGetOnTrain_UpdateFSM, rage_aiTask_SetState, CTrain_FindClosestBoardingPoint, SimdShuffleOp, SimdLoadLane, LoadZero...; globals 25408152, 5239416

### CTaskGetOffTrain_UpdateFSM (lines 5017230–5017395, 167 lines)

FSM state-machine update (per-frame behavior); calls CTaskGetOffTrain_UpdateFSM, rage_aiTask_SetState, CTrain_FindClosestBoardingPoint, SimdShuffleOp, SimdLoadLane, LoadZero...; globals 25408152, 5239416

### cxx_global_array_dtor_4567 (lines 5017397–5017399, 4 lines)

cleanup / shutdown; calls cxx_global_array_dtor_4567, CTuning_CTuning

### CTaskTryToGrabVehicleDoor_CTaskTryToGrabVehicleDoor_1 (lines 5017401–5017439, 40 lines)

constructor / variant; calls CTaskTryToGrabVehicleDoor_CTaskTryToGrabVehicleDoor_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip, rage_aiTask_aiTask_1; globals 12321880; 2 vtable call(s); 1 loop(s); 2 atomic op(s)

### CTaskTryToGrabVehicleDoor_CTaskTryToGrabVehicleDoor_123479 (lines 5017441–5017444, 5 lines)

helper; calls CTaskTryToGrabVehicleDoor_CTaskTryToGrabVehicleDoor_123479, CTaskTryToGrabVehicleDoor_CTaskTryToGrabVehicleDoor_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskTryToGrabVehicleDoor_ProcessPreFSM (lines 5017446–5017457, 13 lines)

pre-FSM setup / signal processing; calls CTaskTryToGrabVehicleDoor_ProcessPreFSM, CVehicle_IsEntryIndexValid, CTaskNMBehaviour_CanUseRagdoll_1

### CTaskTryToGrabVehicleDoor_UpdateFSM (lines 5017459–5017587, 130 lines)

FSM state-machine update (per-frame behavior); calls CTaskTryToGrabVehicleDoor_UpdateFSM, rage_aiTask_SetState, CVehicle_GetEntryExitPoint, CVehicleModelInfo_GetEntryPointInfo, CPedIntelligence_CreateCloneTaskForTaskType, rage_fwRegdRef_rage_fwEntity_rage_fwRefAwareBase_Reset...; globals 25334475, 12321248, 25408152, 25448180...; 2 loop(s)

### CTaskTryToGrabVehicleDoor_SetupBalanceGrabHelper (lines 5017589–5017650, 63 lines)

setter; calls CTaskTryToGrabVehicleDoor_SetupBalanceGrabHelper, CVehicle_GetEntryExitPoint, CVehicleModelInfo_GetEntryPointInfo, CEntity_GetCollider, rage_fragInst_GetControllingComponentFromBoneIndex, rage_Matrix34_Dot...; globals 25448192, 25448208; 2 vtable call(s); 2 atomic op(s)

### CTaskTryToGrabVehicleDoor_AddGetUpSets (lines 5017652–5017714, 64 lines)

query / predicate; calls CTaskTryToGrabVehicleDoor_AddGetUpSets, CAITarget_CAITarget_1, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, rage_aiTask_aiTask, CAITarget_CAITarget_4...; globals 25408152, 15567136, 10854468, 10854472...; 1 loop(s)

### cxx_global_array_dtor_4573 (lines 5017716–5017718, 4 lines)

cleanup / shutdown; calls cxx_global_array_dtor_4573, CTuning_CTuning

### CTaskVehicleFSM_GetEntryRadiusMultiplier (lines 5017720–5017728, 10 lines)

query / predicate; calls CTaskVehicleFSM_GetEntryRadiusMultiplier; globals 25446240, 25446244

### CTaskVehicleFSM_ShouldClipSetBeStreamedOut (lines 5017730–5017744, 16 lines)

setter; calls CTaskVehicleFSM_ShouldClipSetBeStreamedOut, CPrioritizedClipSetRequestManager_ShouldClipSetBeStreamedOut; globals 10854472, 24012584

### CTaskVehicleFSM_SetScriptedVehicleEntryExitFlags (lines 5017746–5017764, 20 lines)

setter; calls CTaskVehicleFSM_SetScriptedVehicleEntryExitFlags

### CTaskVehicleFSM_GetExitToAimClipSetIdForPed (lines 5017766–5017858, 94 lines)

query / predicate; calls CTaskVehicleFSM_GetExitToAimClipSetIdForPed, CPedWeaponSelector_GetBestPedWeapon, CWeaponItem_GetKeyFromHash, CSeatManager_GetPedsSeatIndex, CVehicle_GetSeatAnimationInfo; globals 25445648, 25445640, 10854472; 4 loop(s)

### CTaskVehicleFSM_GetDoorForEntryPointIndex_1 (lines 5017860–5017869, 11 lines)

query / predicate; calls CTaskVehicleFSM_GetDoorForEntryPointIndex_1, CModelSeatInfo_GetBoneIndexFromEntryPoint, CVehicle_GetDoorFromBoneIndex_1

### CTaskVehicleFSM_GetPedsGroupPlayerLeader (lines 5017871–5017882, 13 lines)

query / predicate; calls CTaskVehicleFSM_GetPedsGroupPlayerLeader, CPedGroups_GetPedsGroup

### CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug (lines 5017884–5017966, 84 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug, rage_aiTask_aiTask, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_New, rage_sysCriticalSectionToken_Unlock, rage_fwKnownRefHolder_fwKnownRefHolder...; globals 15567136, 10854468, 10854472, 12321880; 2 loop(s)

### CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug_1 (lines 5017968–5018021, 55 lines)

constructor / variant; calls CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug_1, operator_delete, rage_fwClipSetRequestHelper_fwClipSetRequestHelper, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock...; globals 12321880; 3 vtable call(s); 1 loop(s); 2 atomic op(s)

### CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug_123502 (lines 5018023–5018026, 5 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug_123502, CTaskAttachedVehicleAnimDebug_CTaskAttachedVehicleAnimDebug_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskAttachedVehicleAnimDebug_CleanUp (lines 5018028–5018038, 12 lines)

cleanup / shutdown; calls CTaskAttachedVehicleAnimDebug_CleanUp, CPed_SetPedOutOfVehicle, CMovePed_ClearTaskNetwork, rage_fwAnimDirector_GetMove; 1 vtable call(s)

### CTaskAttachedVehicleAnimDebug_ProcessPreFSM (lines 5018040–5018053, 15 lines)

pre-FSM setup / signal processing; calls CTaskAttachedVehicleAnimDebug_ProcessPreFSM

### CTaskAttachedVehicleAnimDebug_ProcessPhysics (lines 5018055–5018106, 53 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_ProcessPhysics, CPed_ApplyAnimatedVelocityWhilstAttached, CTaskAttachedVehicleAnimDebug_ComputeIdealEndTransformForState, CTaskAttachedVehicleAnimDebug_GetClipBlendParamsForState, CTaskVehicleFSM_ApplyMoverFixup, operator_delete; globals 26613668

### CTaskAttachedVehicleAnimDebug_ComputeIdealEndTransformForState (lines 5018108–5018475, 369 lines)

calculation (math/geometry/route); calls CTaskAttachedVehicleAnimDebug_ComputeIdealEndTransformForState, CTaskAttachedVehicleAnimDebug_ComputeIdealStartTransformForState, CVehicleModelInfo_GetEntryPointAnimInfo, CModelSeatInfo_GetBoneIndexFromEntryPoint, CModelSeatInfo_CalculateSeatSituation, CTaskAttachedVehicleAnimDebug_GetClipBlendParamsForState...; globals 26613668

### CTaskAttachedVehicleAnimDebug_GetClipBlendParamsForState (lines 5018477–5018558, 83 lines)

query / predicate; calls CTaskAttachedVehicleAnimDebug_GetClipBlendParamsForState, CMoveNetworkHelper_GetFloat, rage_atArray_float_0_Grow, CTaskAttachedVehicleAnimDebug_GetClipArrayForState, CTaskVehicleFSM_PreComputeStaticBlendWeightsFromSignal, rage_atHashStringNamespaceSupport_AddString...; globals 26613712, 10854472, 10854468; 1 loop(s)

### CTaskAttachedVehicleAnimDebug_ComputeIdealStartTransformForState (lines 5018560–5019016, 458 lines)

calculation (math/geometry/route); calls CTaskAttachedVehicleAnimDebug_ComputeIdealStartTransformForState, rage_atHashStringNamespaceSupport_AddString, CTaskAttachedVehicleAnimDebug_GetClipIdForState, rage_fwClipSetManager_GetClip, rage_fwAnimHelpers_GetMoverTrackTranslationDiff, rage_fwAnimHelpers_GetMoverTrackRotation...; globals 10854472, 10854468, 26613668

### CTaskAttachedVehicleAnimDebug_GetClipArrayForState (lines 5019018–5019093, 77 lines)

query / predicate; calls CTaskAttachedVehicleAnimDebug_GetClipArrayForState, rage_atHashStringNamespaceSupport_AddString, rage_atArray_rage_atNonFinalHashString_0_Grow, rage_fwClipSetManager_GetClip, rage_atArray_rage_restService_0_Grow, operator_delete; globals 10854472, 10854468; 1 loop(s)

### CTaskAttachedVehicleAnimDebug_GetClipIdForState (lines 5019095–5019182, 89 lines)

query / predicate; calls CTaskAttachedVehicleAnimDebug_GetClipIdForState, rage_bkManager_FindBank, rage_bkManager_IsBankThread, rage_bkGroup_AddToggle_1, CDebugScene_QueueTuneWidget, CDebugScene_TuneWidgetData_TuneWidgetData...; globals 25449300, 8350384, 7736812, 10854468; 1 atomic op(s)

### CTaskAttachedVehicleAnimDebug_IsMoveTransitionAvailable (lines 5019184–5019228, 46 lines)

query / predicate; calls CTaskAttachedVehicleAnimDebug_IsMoveTransitionAvailable

### CTaskAttachedVehicleAnimDebug_Align_OnUpdate (lines 5020282–5020325, 45 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_Align_OnUpdate, rage_diagLogf2, CMoveNetworkHelperFunctions_IsMoveNetworkStateFinished, CTaskClimbLadder_SetTaskState; globals 11547195, 12321252; 3 vtable call(s)

### CTaskAttachedVehicleAnimDebug_OpenDoor_OnEnter (lines 5020327–5020334, 9 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_OpenDoor_OnEnter, CTaskAttachedVehicleAnimDebug_SetUpMoveParamsAndAttachState, CMoveNetworkHelperFunctions_SetMoveNetworkState

### CTaskAttachedVehicleAnimDebug_OpenDoor_OnUpdate (lines 5020336–5020430, 96 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_OpenDoor_OnUpdate, rage_diagLogf2, rage_atHashStringNamespaceSupport_AddString, CTaskAttachedVehicleAnimDebug_GetClipIdForState, rage_fwClipSetManager_GetClip, CTaskAttachedVehicleAnimDebug_ProcessDoorAngle...; globals 11547195, 12321252, 10854472, 10854468; 3 vtable call(s)

### CTaskAttachedVehicleAnimDebug_CloseDoorFromInside_OnUpdate (lines 5020432–5020526, 96 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_CloseDoorFromInside_OnUpdate, rage_diagLogf2, rage_atHashStringNamespaceSupport_AddString, CTaskAttachedVehicleAnimDebug_GetClipIdForState, rage_fwClipSetManager_GetClip, CTaskAttachedVehicleAnimDebug_ProcessDoorAngle...; globals 11547195, 12321252, 10854472, 10854468; 3 vtable call(s)

### CTaskAttachedVehicleAnimDebug_CloseDoorFromOutside_OnEnter (lines 5020528–5020535, 9 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_CloseDoorFromOutside_OnEnter, CTaskAttachedVehicleAnimDebug_SetUpMoveParamsAndAttachState, CMoveNetworkHelperFunctions_SetMoveNetworkState

### CTaskAttachedVehicleAnimDebug_AttachPedForState (lines 5020537–5020747, 212 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_AttachPedForState, CTaskAttachedVehicleAnimDebug_ComputeIdealStartTransformForState, i32x4_bitmask, f32x4_abs, SimdShuffleOp, f32x4_mul...; 2 vtable call(s)

### CTaskAttachedVehicleAnimDebug_SetUpMoveParamsAndAttachState (lines 5020749–5020882, 135 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_SetUpMoveParamsAndAttachState, CTaskAttachedVehicleAnimDebug_AttachPedForState, CTaskAttachedVehicleAnimDebug_GetClipArrayForState, CMoveNetworkHelper_SetClip, operator_delete, CTaskAttachedVehicleAnimDebug_GetClipIdForState...; globals 25448236, 25448240, 25448244, 25448248...; 1 vtable call(s); 1 loop(s)

### CTaskAttachedVehicleAnimDebug_ProcessDoorAngle (lines 5020884–5020951, 69 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_ProcessDoorAngle, CModelSeatInfo_GetBoneIndexFromEntryPoint, CVehicle_GetDoorFromBoneIndex, CClipEventTags_CTagIteratorAttributeValue_rage_crTag_rage_crPropertyAttributeBool_bool_CTagIteratorA, CTaskVehicleFSM_DriveDoorFromClip; globals 15569880, 15569900

### CTaskAttachedVehicleAnimDebug_ProcessPostFSM (lines 5020953–5021018, 67 lines)

debug / diagnostics; calls CTaskAttachedVehicleAnimDebug_ProcessPostFSM, rage_bkManager_FindBank, rage_bkManager_IsBankThread, rage_bkGroup_AddToggle_1, CDebugScene_QueueTuneWidget, CDebugScene_TuneWidgetData_TuneWidgetData...; globals 25449280, 8350384, 7736800; 1 atomic op(s)

### CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon (lines 5021020–5021087, 69 lines)

helper; calls CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon, rage_aiTask_aiTask, CAITarget_CAITarget, CAITarget_CAITarget_4, rage_fwRegdRef_rage_fwEntity_rage_fwRefAwareBase_Reset, rage_sysCriticalSectionToken_Lock...; globals 15567136, 10854468, 10854472, 10852368...; 1 loop(s)

### CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon_1 (lines 5021089–5021146, 59 lines)

constructor / variant; calls CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip, rage_aiTask_aiTask_1; globals 12321880; 2 vtable call(s); 2 loop(s); 2 atomic op(s)

### CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon_123558 (lines 5021148–5021151, 5 lines)

helper; calls CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon_123558, CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskVehicleMountedWeapon_ProcessPostCamera (lines 5021153–5021167, 16 lines)

processing / event handling; calls CTaskVehicleMountedWeapon_ProcessPostCamera, CSeatManager_GetPedsSeatIndex, CTaskVehicleMountedWeapon_ControlVehicleWeapons

### CTaskVehicleMountedWeapon_ProcessMoveSignals (lines 5022609–5022625, 18 lines)

processing / event handling; calls CTaskVehicleMountedWeapon_ProcessMoveSignals, CSeatManager_GetPedsSeatIndex, CTaskVehicleMountedWeapon_ControlVehicleWeapons

### CTaskVehicleMountedWeapon_ProcessPostPreRenderAfterAttachments (lines 5022627–5022655, 30 lines)

processing / event handling; calls CTaskVehicleMountedWeapon_ProcessPostPreRenderAfterAttachments, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25449308, 8350384, 25449304; 1 atomic op(s)

### CTaskVehicleMountedWeapon_Debug (lines 5022657–5022721, 66 lines)

debug / diagnostics; calls CTaskVehicleMountedWeapon_Debug, rage_grcDebugDraw_Sphere, CPedWeaponManager_GetEquippedVehicleWeapon, rage_formatf_128ul, rage_grcDebugDraw_Text_3, i64_extend_i32_s; globals 19622724, 12321248; 3 vtable call(s); 1 loop(s)

### CTaskVehicleMountedWeapon_UpdateFSM (lines 5022723–5022855, 134 lines)

FSM state-machine update (per-frame behavior); calls CTaskVehicleMountedWeapon_UpdateFSM, CTaskVehicleMountedWeapon_StreamingClips_OnUpdate, CTaskVehicleMountedWeapon_Idle_OnEnter, CTaskVehicleMountedWeapon_Idle_OnUpdate, CSeatManager_GetPedsSeatIndex, CVehicleWeaponMgr_GetFirstFixedWeaponForSeat...; globals 19235320, 28463163

### CTaskVehicleMountedWeapon_StreamingClips_OnUpdate (lines 5022857–5022914, 59 lines)

helper; calls CTaskVehicleMountedWeapon_StreamingClips_OnUpdate, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25449312, 8350384, 7736820, 15562208; 1 vtable call(s); 1 atomic op(s)

### CTaskVehicleMountedWeapon_Idle_OnEnter (lines 5022916–5022952, 38 lines)

helper; calls CTaskVehicleMountedWeapon_Idle_OnEnter, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, rage_aiTask_SetNewTask, CTaskAmbientClips_CTaskAmbientClips; globals 25408152, 15584256, 25444816; 1 loop(s)

### CTaskVehicleMountedWeapon_Idle_OnUpdate (lines 5022954–5023017, 65 lines)

helper; calls CTaskVehicleMountedWeapon_Idle_OnUpdate, i64_extend_i32_s, CVehicle_GetSeatAnimationInfo_1, CTaskVehicleMountedWeapon_WantsToFire, CTaskVehicleMountedWeapon_CanFireAtTarget, CTaskVehicleMountedWeapon_ShouldPreventAimingOrFiringDueToLookBehind...; 1 vtable call(s); 1 loop(s)

### CTaskVehicleMountedWeapon_GetTargetInfo (lines 5023019–5023544, 527 lines)

query / predicate; calls CTaskVehicleMountedWeapon_GetTargetInfo, CSyncedEntity_GetEntity, CAITarget_GetIsValid, CAITarget_GetPosition, rage_bkManager_FindBank, rage_bkManager_IsBankThread...; globals 25449448, 8350384, 7736940, 25449456...; 12 vtable call(s); 5 atomic op(s)

### CTaskVehicleMountedWeapon_WantsToFire (lines 5023546–5023628, 84 lines)

helper; calls CTaskVehicleMountedWeapon_WantsToFire, i32_wrap_i64, CTaskVehicleMountedWeapon_ShouldPreventAimingOrFiringDueToLookBehind, CPlayerInfo_IsFiring, CVehicleWeaponMgr_GetWeaponsForSeat, CSeatManager_GetPedsSeatIndex...; 4 vtable call(s)

### CTaskVehicleMountedWeapon_CanFireAtTarget (lines 5023630–5023663, 35 lines)

helper; calls CTaskVehicleMountedWeapon_CanFireAtTarget, CPedWeaponManager_GetEquippedWeapon, CPed_IsAllowedToDamageEntity, i64_extend8_s

### CTaskVehicleMountedWeapon_ShouldPreventAimingOrFiringDueToLookBehind (lines 5023665–5023721, 58 lines)

helper; calls CTaskVehicleMountedWeapon_ShouldPreventAimingOrFiringDueToLookBehind, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25449496, 8350384, 25449492, 25449500...; 2 atomic op(s)

### CTaskVehicleMountedWeapon_ComputeSearchTarget (lines 5023723–5024049, 328 lines)

calculation (math/geometry/route); calls CTaskVehicleMountedWeapon_ComputeSearchTarget, i64_extend_i32_s, CSyncedEntity_GetEntity, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup...; globals 25449408, 8350384, 25449412, 25449416...; 1 vtable call(s); 1 loop(s); 10 atomic op(s)

### CTaskVehicleMountedWeapon_ProcessPreFSM (lines 5024051–5024383, 334 lines)

pre-FSM setup / signal processing; calls CTaskVehicleMountedWeapon_ProcessPreFSM, NetworkInterface_ForceSynchronisation, CSeatManager_GetPedsSeatIndex, CNetObjPed_GetWeaponData, CNetObjPed_SetWeaponData, CTaskVehicleMountedWeapon_IsTaskValid...; globals 25449484, 8350384, 25449480, 19623124...; 7 vtable call(s); 1 loop(s); 2 atomic op(s)

### CTaskVehicleMountedWeapon_EvaluateTerrainForFireDirection (lines 5024385–5024889, 506 lines)

helper; calls CTaskVehicleMountedWeapon_EvaluateTerrainForFireDirection, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25449364, 8350384, 25449368, 25449372...; 1 vtable call(s); 1 loop(s); 11 atomic op(s)

### CTaskVehicleMountedWeapon_GetVehicleTargetingFlags (lines 5024891–5024930, 41 lines)

query / predicate; calls CTaskVehicleMountedWeapon_GetVehicleTargetingFlags, CPed_GetControlFromPlayer, rage_ioValue_IsPressed, CPlayerInfo_IsSelectingLeftTarget, CPlayerInfo_IsSelectingRightTarget; globals 4334628; 3 vtable call(s)

### CTaskVehicleMountedWeapon_FindTarget (lines 5024932–5025022, 92 lines)

helper; calls CTaskVehicleMountedWeapon_FindTarget, CDebugDrawStore_ClearAll, CPedTargetEvaluator_FindTarget_1; globals 20212396, 6105332, 20212548, 20212569...; 1 vtable call(s)

### CTaskVehicleMountedWeapon_WantsToAim (lines 5025024–5025041, 19 lines)

helper; calls CTaskVehicleMountedWeapon_WantsToAim, CTaskVehicleMountedWeapon_ShouldPreventAimingOrFiringDueToLookBehind, CSeatManager_GetPedsSeatIndex, CVehicle_IsTurretSeat, CPlayerInfo_IsAiming

### CTaskVehicleMountedWeapon_DoTerrainProbe (lines 5025043–5025078, 37 lines)

helper; calls CTaskVehicleMountedWeapon_DoTerrainProbe, WorldProbe_CShapeTestDesc_SetResultsStructure, WorldProbe_CShapeTestDesc_SetExcludeEntity, WorldProbe_CShapeTestManager_DebugSubmitTest, WorldProbe_CShapeTestManager_AbortTest, WorldProbe_CShapeTestResults_FreeIntersections

### CTaskVehicleMountedWeapon_CreateQueriableState (lines 5025080–5025231, 153 lines)

helper; calls CTaskVehicleMountedWeapon_CreateQueriableState, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25449508, 8350384, 25449516, 25449504...; 2 vtable call(s); 3 atomic op(s)

### CTaskVehicleMountedWeapon_ReadQueriableState (lines 5025233–5025256, 25 lines)

helper; calls CTaskVehicleMountedWeapon_ReadQueriableState, CSyncedEntity_GetEntity, CAITarget_SetEntity, CAITarget_SetPosition; 2 vtable call(s)

### CTaskVehicleMountedWeapon_CleanUp (lines 5025258–5025260, 4 lines)

cleanup / shutdown; calls CTaskVehicleMountedWeapon_CleanUp, CTaskGun_ClearToggleAim

### CTaskVehicleMountedWeapon_UpdateClonedFSM (lines 5025262–5025447, 187 lines)

helper; calls CTaskVehicleMountedWeapon_UpdateClonedFSM, rage_aiTask_SetState, CTaskVehicleMountedWeapon_StreamingClips_OnUpdate, CTaskVehicleMountedWeapon_Idle_OnEnter, CTaskVehicleMountedWeapon_Idle_OnUpdate, CSeatManager_GetPedsSeatIndex...; globals 12321248, 26019728, 28463163; 4 vtable call(s); 1 atomic op(s)

### CTaskVehicleMountedWeapon_CreateTaskForClonePed (lines 5025449–5025471, 24 lines)

helper; calls CTaskVehicleMountedWeapon_CreateTaskForClonePed, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, CTaskVehicleMountedWeapon_CTaskVehicleMountedWeapon; globals 25408152

### CClonedControlTaskVehicleMountedWeaponInfo_CClonedControlTaskVehicleMountedWeaponInfo (lines 5025473–5025495, 24 lines)

helper; calls CClonedControlTaskVehicleMountedWeaponInfo_CClonedControlTaskVehicleMountedWeaponInfo, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock; globals 12321880; 1 loop(s)

### CClonedControlTaskVehicleMountedWeaponInfo_CClonedControlTaskVehicleMountedWeaponInfo_123596 (lines 5025497–5025519, 24 lines)

helper; calls CClonedControlTaskVehicleMountedWeaponInfo_CClonedControlTaskVehicleMountedWeaponInfo_123596, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, rage_sysMemPoolAllocator_Free; globals 12321880, 20217488; 1 loop(s)

### CClonedControlTaskVehicleMountedWeaponInfo_CreateCloneFSMTask (lines 5025521–5025584, 65 lines)

helper; calls CClonedControlTaskVehicleMountedWeaponInfo_CreateCloneFSMTask, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, rage_aiTask_aiTask, CAITarget_CAITarget, CSyncedEntity_GetEntity...; globals 25408152, 15567136, 10854468, 10854472...

### CClonedVehicleGunInfo_CreateCloneFSMTask (lines 5025586–5025631, 47 lines)

helper; calls CClonedVehicleGunInfo_CreateCloneFSMTask, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, rage_aiTask_aiTask, CAITarget_CAITarget, rage_fwClipSetRequestHelper_fwClipSetRequestHelper_1...; globals 25408152, 15567136, 10854468, 10854472

### CTaskVehicleGun_CTaskVehicleGun_1 (lines 5025633–5025672, 41 lines)

constructor / variant; calls CTaskVehicleGun_CTaskVehicleGun_1, rage_fwClipSetRequestHelper_fwClipSetRequestHelper, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CClipHelper_StopClip...; globals 12321880; 2 vtable call(s); 1 loop(s); 2 atomic op(s)

### CTaskVehicleGun_CTaskVehicleGun_123601 (lines 5025674–5025677, 5 lines)

helper; calls CTaskVehicleGun_CTaskVehicleGun_123601, CTaskVehicleGun_CTaskVehicleGun_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskVehicleGun_ProcessPreFSM (lines 5025679–5025940, 263 lines)

pre-FSM setup / signal processing; calls CTaskVehicleGun_ProcessPreFSM, CVehicleMetadataMgr_CanPedDoDriveByWithEquipedWeapon, CPedWeaponManager_GetEquippedVehicleWeapon, CWeaponInfo_CanBeUsedAsDriveBy, CSyncedEntity_GetEntity, SimdLaneOp...; globals 28496584, 28496576, 28501281, 11547184...; 3 vtable call(s); 1 loop(s)

### CTaskVehicleGun_GetTargetPosition (lines 5025942–5025995, 55 lines)

query / predicate; calls CTaskVehicleGun_GetTargetPosition, i32_wrap_i64, CPedWeaponManager_GetEquippedWeapon_1, CWeapon_CalcFireVecFromAimCamera, camInterface_GetPlayerControlCamAimFrame, SimdLaneOp...

### CTaskVehicleGun_UpdateFSM (lines 5025997–5026078, 83 lines)

FSM state-machine update (per-frame behavior); calls CTaskVehicleGun_UpdateFSM, CTaskVehicleGun_Init_OnUpdate, rage_aiTask_SetState, rage_fwClipSetRequestHelper_Request, CTaskVehicleGun_SmashWindow_OnEnter, rage_aiTaskTree_FindTaskByTypeActive...

### CTaskVehicleGun_Init_OnUpdate (lines 5026080–5026231, 153 lines)

initialization; calls CTaskVehicleGun_Init_OnUpdate, CFiringPattern_SetFiringPattern, CVehicleMetadataMgr_GetVehicleDriveByInfoFromPed, CTaskVehicleGun_SelectClipSet, CVehicleDriveByInfo_GetMinRestrictedAimSweepHeadingAngleDegs, CVehicleDriveByInfo_GetMaxRestrictedAimSweepHeadingAngleDegs...; globals 10854472, 25449520; 1 atomic op(s)

### CTaskVehicleGun_SmashWindow_OnEnter (lines 5026233–5026321, 90 lines)

helper; calls CTaskVehicleGun_SmashWindow_OnEnter, CVehicle_GetSeatAnimationInfo_1, CVehicleSeatAnimInfo_FindAnim, CPed_IsInFirstPersonVehicleCamera, CTaskVehicleGun_GetDoorForPed, CVehicle_DoesVehicleHaveAConvertibleRoofAnimation...; globals 25408152, 15567136, 10854468, 10854472

### CTaskVehicleGun_WaitingToFire_OnUpdate (lines 5026323–5026519, 198 lines)

helper; calls CTaskVehicleGun_WaitingToFire_OnUpdate, rage_aiTask_SetState, CPedWeaponManager_GetIsArmedMelee, CWeaponInfo_GetAmmoInfo, CAmmoItemRepository_GetAmmo, CPedWeaponManager_EquipBestWeapon...; globals 28496584, 28496576, 15562208; 2 vtable call(s); 1 loop(s)

### CTaskVehicleGun_Gun_OnEnter (lines 5026521–5026851, 332 lines)

helper; calls CTaskVehicleGun_Gun_OnEnter, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, CAITarget_CAITarget_4, CSyncedEntity_GetEntity, CAITarget_CAITarget_1...; globals 28484732, 25408152, 12321880; 10 loop(s)

### CTaskVehicleGun_Gun_OnUpdate (lines 5026853–5027112, 261 lines)

helper; calls CTaskVehicleGun_Gun_OnUpdate, CPed_IsInFirstPersonVehicleCamera, CPed_IsFirstPersonShooterModeEnabledForPlayer, ReportPlayerResetMismatch, CPedWeaponManager_GetEquippedVehicleWeapon, CVehicleMetadataMgr_GetDriveByAnimInfoForWeapon...; globals 28496584, 28496576, 10854472; 2 vtable call(s); 3 loop(s)

### CTaskVehicleGun_SelectClipSet (lines 5027114–5027196, 84 lines)

setter; calls CTaskVehicleGun_SelectClipSet, CPedWeaponManager_GetEquippedVehicleWeapon, CVehicleMetadataMgr_GetDriveByAnimInfoForWeapon, CTaskAimGunVehicleDriveBy_CanUseRestrictedDrivebyAnims, CTaskAimGunVehicleDriveBy_ShouldUseRestrictedDrivebyAnimsOrBlockingIK, CPed_IsInFirstPersonVehicleCamera...; globals 28496584, 28496576, 10854472; 1 vtable call(s); 1 loop(s)

### CTaskVehicleGun_GetRestrictedAimSweepHeadingAngleRads (lines 5027198–5027264, 68 lines)

query / predicate; calls CTaskVehicleGun_GetRestrictedAimSweepHeadingAngleRads, CVehicleMetadataMgr_GetVehicleDriveByInfoFromPed, CPedWeaponManager_GetEquippedVehicleWeapon, CVehicleMetadataMgr_GetDriveByAnimInfoForWeapon, CVehicleDriveByInfo_GetMinRestrictedAimSweepHeadingAngleDegs, CVehicleDriveByInfo_GetMaxRestrictedAimSweepHeadingAngleDegs...; globals 28496584, 28496576, 20159720; 1 vtable call(s); 1 loop(s)

### CTaskVehicleGun_CheckFiringConditions (lines 5027266–5027377, 113 lines)

helper; calls CTaskVehicleGun_CheckFiringConditions, CPed_IsInFirstPersonVehicleCamera, rage_diagDisplayf, camGameplayDirector_IsAiming, camInterface_GetPlayerControlCamAimFrame, CPedWeaponManager_GetEquippedVehicleWeapon...; globals 25458448, 12321252, 19235320; 2 vtable call(s)

### CTaskVehicleGun_ProcessWeaponObject (lines 5027379–5027416, 39 lines)

processing / event handling; calls CTaskVehicleGun_ProcessWeaponObject, CPedWeaponManager_GetEquippedVehicleWeapon, CPedEquippedWeapon_AttachObject, CPedWeaponManager_GetRequiresWeaponSwitch, CPedInventory_GetIsStreamedIn, CPedWeaponManager_CreateEquippedWeaponObject...; 1 vtable call(s)

### CTaskVehicleGun_CleanUp (lines 5027418–5027428, 12 lines)

cleanup / shutdown; calls CTaskVehicleGun_CleanUp, CClipHelper_StopClip, CTaskVehicleGun_GetDoorForPed, CCarDoor_SetSwingingFree, CTaskGun_ClearToggleAim

### CTaskMotionInVehicle_GetSeatOverrideAnimInfoFromPed (lines 5027430–5027447, 19 lines)

query / predicate; calls CTaskMotionInVehicle_GetSeatOverrideAnimInfoFromPed, CVehicle_GetSeatAnimationInfo_1, CPed_GetPrimaryMotionTask, CVehicleMetadataMgr_GetInVehicleOverrideInfo, CInVehicleOverrideInfo_FindSeatOverrideAnimInfoFromSeatAnimInfo

### CTaskVehicleGun_CreateQueriableState (lines 5027449–5027473, 26 lines)

helper; calls CTaskVehicleGun_CreateQueriableState, CAITarget_GetIsValid, CAITarget_GetPosition, rage_sysMemPoolAllocator_Allocate, Quitf_1, CSyncedEntity_GetEntity...; globals 10852368, 20217488

### CTaskVehicleGun_ReadQueriableState (lines 5027475–5027488, 15 lines)

helper; calls CTaskVehicleGun_ReadQueriableState, CSyncedEntity_GetEntity, CAITarget_SetEntity, CAITarget_SetPosition; 2 vtable call(s)

### CTaskVehicleGun_UpdateClonedFSM (lines 5027490–5027604, 116 lines)

helper; calls CTaskVehicleGun_UpdateClonedFSM, CTaskVehicleGun_Init_OnUpdate, rage_aiTask_SetState, rage_fwClipSetRequestHelper_Request, CTaskVehicleGun_SmashWindow_OnEnter, rage_aiTaskTree_FindTaskByTypeActive...

### CTaskVehicleGun_IsInScope (lines 5027606–5027650, 46 lines)

query / predicate; calls CTaskVehicleGun_IsInScope, CTaskFSMClone_IsInScope, CVehicleMetadataMgr_CanPedDoDriveByWithEquipedWeapon, CWeaponInfo_CanBeUsedAsDriveBy; globals 28496584, 28496576; 1 loop(s)

### CTaskVehicleGun_Debug (lines 5027652–5028194, 544 lines)

debug / diagnostics; calls CTaskVehicleGun_Debug, i32x4_bitmask, CTaskAimGun_CalculateDesiredYaw, CTaskAimGun_CalculateDesiredPitch, f64_promote_f32, rage_grcDebugDraw_AddDebugOutput_1...; globals 25459816, 25458509, 7742864, 7742862...; 1 vtable call(s)

### CTaskVehicleProjectile_CTaskVehicleProjectile (lines 5028196–5028225, 31 lines)

helper; calls CTaskVehicleProjectile_CTaskVehicleProjectile, rage_aiTask_aiTask, rage_fwClipSetRequestHelper_fwClipSetRequestHelper_1; globals 15567136, 10854468, 10854472

### CTaskVehicleProjectile_ProcessPreFSM (lines 5028227–5028305, 80 lines)

pre-FSM setup / signal processing; calls CTaskVehicleProjectile_ProcessPreFSM, i32_wrap_i64, CPed_GetControlFromPlayer, CControl_IsVehicleAttackInputReleased, rage_ioValue_IsDown, CVehicle_ContainsPed...; globals 4334628, 12839924

### CTaskVehicleProjectile_CreateQueriableState (lines 5028307–5028325, 20 lines)

helper; calls CTaskVehicleProjectile_CreateQueriableState, rage_sysMemPoolAllocator_Allocate, Quitf_1, CTaskInfo_CTaskInfo; globals 20217488

### CTaskVehicleProjectile_ReadQueriableState (lines 5028327–5028332, 7 lines)

helper; calls CTaskVehicleProjectile_ReadQueriableState; 2 vtable call(s)

### CTaskVehicleProjectile_UpdateClonedFSM (lines 5028334–5028348, 16 lines)

helper; calls CTaskVehicleProjectile_UpdateClonedFSM, rage_aiTask_SetState; 1 vtable call(s)

### CTaskVehicleProjectile_IsInScope (lines 5028350–5028390, 42 lines)

query / predicate; calls CTaskVehicleProjectile_IsInScope, CTaskFSMClone_IsInScope, CVehicleMetadataMgr_CanPedDoDriveByWithEquipedWeapon, CWeaponInfo_CanBeUsedAsDriveBy; globals 28496584, 28496576; 1 loop(s)

### CTaskVehicleProjectile_UpdateFSM (lines 5028392–5028840, 450 lines)

FSM state-machine update (per-frame behavior); calls CTaskVehicleProjectile_UpdateFSM, CVehicleMetadataMgr_GetDriveByAnimInfoForWeapon, CPed_IsInFirstPersonVehicleCamera, CPed_IsFirstPersonShooterModeEnabledForPlayer, CVehicleDriveByAnimInfo_GetFirstPersonClipSet, rage_aiTask_SetState...; globals 10854472, 25408152, 15567136, 10854468...; 1 loop(s)

### CTaskVehicleProjectile_GetTargetPosition (lines 5028842–5028951, 111 lines)

query / predicate; calls CTaskVehicleProjectile_GetTargetPosition, CSeatManager_GetPedsSeatIndex, CModelSeatInfo_GetBoneIndexFromSeat, i64_extend_i32_s, CPedWeaponManager_GetEquippedWeapon_1, rage_crSkeletonData_ConvertBoneIdToIndex...; globals 28494092; 6 vtable call(s)

### CSimpleBlendHelper_SetPhase (lines 5028953–5029002, 51 lines)

setter; calls CSimpleBlendHelper_SetPhase, cxa_guard_acquire, rage_atHashStringNamespaceSupport_AddString, cxa_guard_release, rage_mvParameterBuffer_GenerateFreeCapacity, i64_extend_i32_s; globals 25276984, 25276988, 25276992; 1 atomic op(s)

### CTaskVehicleProjectile_ThrowProjectileImmediately (lines 5029004–5029097, 95 lines)

helper; calls CTaskVehicleProjectile_ThrowProjectileImmediately, CPedWeaponManager_GetEquippedWeapon, CTaskVehicleProjectile_GetTargetPosition, rage_crSkeletonData_ConvertBoneIdToIndex, CWeaponInfo_GetProjectileFuseTime, CWeapon_GetCookTimeLeft...; globals 28494092, 12321248; 5 vtable call(s)

### CTaskVehicleProjectile_CleanUp (lines 5029099–5029112, 15 lines)

cleanup / shutdown; calls CTaskVehicleProjectile_CleanUp, CPedWeaponManager_DestroyEquippedWeaponObject, CClipHelper_StopClip

### CClonedVehicleProjectileInfo_CreateCloneFSMTask (lines 5029114–5029150, 38 lines)

helper; calls CClonedVehicleProjectileInfo_CreateCloneFSMTask, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, rage_aiTask_aiTask, rage_fwClipSetRequestHelper_fwClipSetRequestHelper_1; globals 25408152, 15567136, 10854468, 10854472

### cxx_global_array_dtor_5037 (lines 5029152–5029154, 4 lines)

cleanup / shutdown; calls cxx_global_array_dtor_5037, CTuning_CTuning

### CTaskMotionInVehicle_CheckForStill (lines 5029156–5029206, 52 lines)

helper; calls CTaskMotionInVehicle_CheckForStill, CVehicle_GetVelocityIncludingReferenceFrame, CBike_IsConsideredStill; globals 25448488, 25448596, 25448532, 25448536...

### CTaskMotionInVehicle_CheckForMovingForwards (lines 5029208–5029231, 25 lines)

helper; calls CTaskMotionInVehicle_CheckForMovingForwards, CVehicle_GetVelocityIncludingReferenceFrame, i64_extend8_s, CPed_GetControlFromPlayer, CTaskVehiclePlayerDrive_IsThePlayerControlInactive, rage_ioValue_GetNorm

### CTaskMotionInVehicle_CheckForShunt (lines 5029233–5029391, 160 lines)

helper; calls CTaskMotionInVehicle_CheckForShunt, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25449764, 8350384, 25449760, 15562208...; 4 vtable call(s); 4 atomic op(s)

### CTaskMotionInVehicle_CheckForReverse (lines 5029393–5029480, 89 lines)

helper; calls CTaskMotionInVehicle_CheckForReverse, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25450376, 8350384, 25450372, 19623876; 1 vtable call(s); 1 atomic op(s)

### CTaskMotionInVehicle_CheckForStartingEngine (lines 5029482–5029585, 105 lines)

helper; calls CTaskMotionInVehicle_CheckForStartingEngine, i64_extend8_s, CVehicle_GetThrottle, CPed_GetControlFromPlayer, rage_ioValue_GetNorm01, rage_aiTaskTree_FindTaskByTypeActive; globals 19623876, 26611264, 26611256, 7806420...; 1 loop(s)

### CTaskMotionInVehicle_CheckForHotwiring (lines 5029587–5029610, 25 lines)

helper; calls CTaskMotionInVehicle_CheckForHotwiring, i64_extend8_s

### GetSteeringLerpScale (lines 5029612–5029640, 30 lines)

query / predicate; calls GetSteeringLerpScale, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25450392, 8350384, 7737024, 12321260; 1 atomic op(s)

### CTaskMotionInVehicle_ComputeSteeringSignal (lines 5029642–5029703, 63 lines)

calculation (math/geometry/route); calls CTaskMotionInVehicle_ComputeSteeringSignal, CHandlingDataMgr_GetHandlingData, GetSteeringLerpScale, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup...; globals 25450396, 8350384, 25450404, 25450400...; 2 atomic op(s)

### CTaskMotionInVehicle_CTaskMotionInVehicle (lines 5029705–5029739, 36 lines)

helper; calls CTaskMotionInVehicle_CTaskMotionInVehicle, CTaskMotionBase_CTaskMotionBase, i32x4_splat; globals 25441356, 25441364, 25441376, 10854472...

### CTaskMotionInVehicle_CTaskMotionInVehicle_1 (lines 5029741–5029790, 51 lines)

constructor / variant; calls CTaskMotionInVehicle_CTaskMotionInVehicle_1, CVehicleClipRequestHelper_CVehicleClipRequestHelper_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CTaskMotionBase_CTaskMotionBase_1; globals 12321880; 1 vtable call(s); 2 loop(s)

### CTaskMotionInVehicle_CTaskMotionInVehicle_123666 (lines 5029792–5029795, 5 lines)

helper; calls CTaskMotionInVehicle_CTaskMotionInVehicle_123666, CTaskMotionInVehicle_CTaskMotionInVehicle_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskMotionInVehicle_CleanUp (lines 5029797–5029823, 28 lines)

cleanup / shutdown; calls CTaskMotionInVehicle_CleanUp, rage_diagLogf2, CModelSeatInfo_GetEntryPointIndexForSeat, CSeatManager_GetPedsSeatIndex, CTaskVehicleFSM_SetRemotePedUsingDoors, i64_extend8_s; globals 25977691

### CTaskMotionInVehicle_ProcessPreFSM (lines 5029825–5030533, 710 lines)

pre-FSM setup / signal processing; calls CTaskMotionInVehicle_ProcessPreFSM, rage_fwRegdRef_rage_fwEntity_rage_fwRefAwareBase_Reset, i64_extend8_s, CSeatManager_GetPedsSeatIndex, CVehicle_GetSeatAnimationInfo_1, CVehicle_GetIsJetSki...; globals 12321248, 28501281, 10854472, 25446197...; 8 vtable call(s); 3 loop(s); 1 atomic op(s)

### CTaskMotionInVehicle_CheckCanPedMoveToDriversSeat (lines 5030535–5030705, 172 lines)

helper; calls CTaskMotionInVehicle_CheckCanPedMoveToDriversSeat, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider_2, rage_bkBank_UnSetCurrentGroup...; globals 25450488, 8350384, 7737080, 15562208...; 7 vtable call(s); 1 loop(s); 1 atomic op(s)

### CTaskMotionInVehicle_UpdateFSM (lines 5030707–5030883, 178 lines)

FSM state-machine update (per-frame behavior); calls CTaskMotionInVehicle_UpdateFSM, rage_fwRegdRef_rage_fwEntity_rage_fwRefAwareBase_Reset, rage_aiTask_SetState, CVehicle_GetSeatAnimationInfo_1, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1...; globals 25408152; 2 loop(s)

### CTaskMotionInAutomobile_CTaskMotionInAutomobile (lines 5030885–5030950, 67 lines)

helper; calls CTaskMotionInAutomobile_CTaskMotionInAutomobile, CTaskMotionBase_CTaskMotionBase, rage_fwClipSetRequestHelper_fwClipSetRequestHelper_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_New, rage_sysCriticalSectionToken_Unlock...; globals 12321880, 25451252, 25451128

### CTaskMotionOnBicycle_CTaskMotionOnBicycle (lines 5030952–5030982, 32 lines)

helper; calls CTaskMotionOnBicycle_CTaskMotionOnBicycle, CTaskMotionBase_CTaskMotionBase, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_New, rage_sysCriticalSectionToken_Unlock, rage_fwKnownRefHolder_fwKnownRefHolder; globals 12321880, 25452716

### CTaskMotionInVehicle_OnBicycle_OnUpdate (lines 5030984–5031013, 31 lines)

helper; calls CTaskMotionInVehicle_OnBicycle_OnUpdate, rage_aiTask_SetState; 1 loop(s)

### CTaskMotionInVehicle_ProcessPostFSM (lines 5031015–5031027, 14 lines)

processing / event handling; calls CTaskMotionInVehicle_ProcessPostFSM, CSeatManager_GetPedsSeatIndex

### CTaskMotionInVehicle_ProcessPostMovement (lines 5031029–5031034, 7 lines)

processing / event handling; calls CTaskMotionInVehicle_ProcessPostMovement, CVehicleClipRequestHelper_Update; globals 12321260

### CTaskMotionInVehicle_ProcessMoveSignals (lines 5031036–5031603, 569 lines)

processing / event handling; calls CTaskMotionInVehicle_ProcessMoveSignals, CVehicle_GetIsJetSki, rage_aiTask_FindSubTaskOfType, CPedHelmetComponent_IsAlreadyWearingAHelmetProp, CPedHelmetComponent_IsHelmetInHand, CPedIKSettingsInfo_IsIKFlagDisabled...; globals 25442847, 11547139, 12321252, 28501281...; 2 vtable call(s); 1 loop(s); 8 atomic op(s)

### CTaskMotionInAutomobile_CheckIfVehicleIsDoingBurnout (lines 5031605–5031710, 107 lines)

query / predicate; calls CTaskMotionInAutomobile_CheckIfVehicleIsDoingBurnout, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider_2, rage_bkBank_UnSetCurrentGroup...; globals 25452392, 8350384, 7737736, 19623876...; 1 vtable call(s); 2 atomic op(s)

### CTaskMotionInAutomobile_IsFirstPersonDrivingBicycle (lines 5031712–5031716, 6 lines)

query / predicate; calls CTaskMotionInAutomobile_IsFirstPersonDrivingBicycle, CPed_IsInFirstPersonVehicleCamera

### CTaskMotionInVehicle_CreatePlayerControlTask (lines 5031718–5031744, 28 lines)

helper; calls CTaskMotionInVehicle_CreatePlayerControlTask, rage_sysMemPoolAllocator_SafeAllocate, Quitf_1, CTaskPlayerDrive_CTaskPlayerDrive, CTaskPlayerOnFoot_CTaskPlayerOnFoot; globals 25408152

### CTaskMotionInVehicle_Debug (lines 5031746–5031750, 6 lines)

debug / diagnostics; calls CTaskMotionInVehicle_Debug, CVehicleClipRequestHelper_Debug; 1 vtable call(s)

### cxx_global_array_dtor_5338 (lines 5031752–5031754, 4 lines)

cleanup / shutdown; calls cxx_global_array_dtor_5338, CTuning_CTuning

### CTaskMotionInAutomobile_WillAbortPuttingOnHelmet (lines 5031756–5031778, 24 lines)

helper; calls CTaskMotionInAutomobile_WillAbortPuttingOnHelmet, CPed_GetControlFromPlayer, rage_ioValue_IsPressed, rage_ioValue_IsDown; globals 4334628, 4334632

### CTaskMotionInAutomobile_IsVehicleDrivable (lines 5031780–5031791, 13 lines)

query / predicate; calls CTaskMotionInAutomobile_IsVehicleDrivable, CVehicleDamage_GetEngineHealth, CVehicle_HasInfiniteFuel

### CTaskMotionInAutomobile_CTaskMotionInAutomobile_1 (lines 5031793–5031823, 32 lines)

constructor / variant; calls CTaskMotionInAutomobile_CTaskMotionInAutomobile_1, CBikeLeanAngleHelper_CBikeLeanAngleHelper, operator_delete, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock...; globals 12321880; 1 loop(s)

### CBikeLeanAngleHelper_CBikeLeanAngleHelper (lines 5031825–5031866, 43 lines)

helper; calls CBikeLeanAngleHelper_CBikeLeanAngleHelper, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock; globals 12321880; 2 loop(s)

### CTaskMotionInAutomobile_CTaskMotionInAutomobile_123694 (lines 5031868–5031871, 5 lines)

helper; calls CTaskMotionInAutomobile_CTaskMotionInAutomobile_123694, CTaskMotionInAutomobile_CTaskMotionInAutomobile_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskMotionInAutomobile_CleanUp (lines 5031873–5031932, 61 lines)

cleanup / shutdown; calls CTaskMotionInAutomobile_CleanUp, SimdStoreLane, LoadZero, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock...; globals 12321880, 15406232, 7277584; 2 loop(s)

### CTaskMotionInAutomobile_CanUsePoVAnims (lines 5033359–5033390, 33 lines)

helper; calls CTaskMotionInAutomobile_CanUsePoVAnims, CTaskMotionInAutomobile_GetSeatClipSetId, cxa_guard_acquire, rage_atHashStringNamespaceSupport_AddString, cxa_guard_release, rage_fwClipSetManager_GetClip...; globals 10854472, 25451540, 19622436; 1 atomic op(s)

### CTaskMotionInAutomobile_CheckForShuntFromHighFall (lines 5033392–5033601, 211 lines)

helper; calls CTaskMotionInAutomobile_CheckForShuntFromHighFall, CPed_IsInFirstPersonVehicleCamera, CVehicle_GetSeatAnimationInfo_1, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup...; globals 25452400, 8350384, 25452404, 25452408...; 6 atomic op(s)

### CTaskMotionInAutomobile_ShouldUseLowriderLeanAltClipset (lines 5033603–5033924, 323 lines)

helper; calls CTaskMotionInAutomobile_ShouldUseLowriderLeanAltClipset, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25452228, 8350384, 25452224, 10854472...; 2 vtable call(s); 1 loop(s); 1 atomic op(s)

### CTaskMotionInAutomobile_GetDefaultClipSetToUse (lines 5033926–5034023, 99 lines)

query / predicate; calls CTaskMotionInAutomobile_GetDefaultClipSetToUse, CTaskMotionInAutomobile_ShouldUseLowriderLean, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1...; globals 25452248, 8350384, 25452244, 10854472; 1 atomic op(s)

### CTaskMotionInAutomobile_GetDefaultClipSetId (lines 5034025–5034098, 75 lines)

query / predicate; calls CTaskMotionInAutomobile_GetDefaultClipSetId, CTaskMotionInAutomobile_GetSeatClipSetId, CVehicle_GetSeatAnimationInfo_1, CPed_IsInFirstPersonVehicleCamera, CVehicle_IsDriver; globals 10854472

### CTaskMotionInAutomobile_ShouldUseBaseIdle (lines 5034100–5034152, 54 lines)

helper; calls CTaskMotionInAutomobile_ShouldUseBaseIdle, i64_extend8_s, CVehicle_GetIsJetSki, CVehicle_GetVelocityIncludingReferenceFrame; globals 25450924, 19622436, 25450928, 12321248...; 2 vtable call(s)

### CTaskMotionInAutomobile_CheckForHelmetVisorSwitch (lines 5034154–5034347, 195 lines)

helper; calls CTaskMotionInAutomobile_CheckForHelmetVisorSwitch, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25451804, 8350384, 25451812, 25451816...; 5 atomic op(s)

### CTaskMotionInAutomobile_GetSeatClipSetId (lines 5034349–5034396, 49 lines)

query / predicate; calls CTaskMotionInAutomobile_GetSeatClipSetId, CVehicle_GetSeatAnimationInfo_1, rage_fwClipSetManager_GetClipSet, CPrioritizedClipSetRequestManager_Request, CPed_IsMale; globals 10854472, 25446197, 24012584, 28501281

### CTaskMotionInAutomobile_StartMoveNetwork (lines 5039567–5039676, 111 lines)

helper; calls CTaskMotionInAutomobile_StartMoveNetwork, CPed_GetPrimaryMotionTask, CVehicleMetadataMgr_GetInVehicleOverrideInfo, CInVehicleOverrideInfo_FindSeatOverrideAnimInfoFromSeatAnimInfo, rage_fwAnimDirector_GetNetworkDef, rage_fwAnimDirector_CreateNetworkPlayer...; globals 15568340, 25449708; 2 vtable call(s)

### CTaskMotionInAutomobile_UpdateFirstPersonAnimationState (lines 5039678–5039777, 101 lines)

helper; calls CTaskMotionInAutomobile_UpdateFirstPersonAnimationState, camInterface_FindFollowPed, CPed_IsInFirstPersonVehicleCamera, CPed_IsFirstPersonShooterModeEnabledForPlayer, CTaskMotionInAutomobile_GetSeatClipSetId, CPrioritizedClipSetRequestManager_IsLoaded...; globals 10854472, 25446197, 24012584, 19235312...

### CTaskMotionInAutomobile_CheckForStartingEngine (lines 5039779–5039798, 21 lines)

helper; calls CTaskMotionInAutomobile_CheckForStartingEngine, CVehicleDamage_GetEngineHealth, CVehicle_HasInfiniteFuel, CTaskMotionInVehicle_CheckForStartingEngine

### CTaskMotionInAutomobile_GetClipForState (lines 5039800–5039853, 55 lines)

query / predicate; calls CTaskMotionInAutomobile_GetClipForState, rage_fwMoveNetworkInterface_GetClipSetId, CPed_IsInFirstPersonVehicleCamera, CPedHelmetComponent_GetAircraftPutOnTakeOffHelmetFPSClipSet, rage_fwClipSetManager_GetClip; globals 10854472, 10854468, 25450796, 25451340

### CTaskMotionInAutomobile_CheckForChangingStation (lines 5039855–5039909, 56 lines)

helper; calls CTaskMotionInAutomobile_CheckForChangingStation, CGameWorld_FindLocalPlayerVehicle, i64_extend8_s, rage_fwMoveNetworkInterface_GetClipSetId, rage_fwClipSetManager_GetClip; globals 19623428, 28501281, 15721255, 15721228...

### CTaskMotionInAutomobile_ShouldUseSitToStillTransition (lines 5039911–5039927, 18 lines)

helper; calls CTaskMotionInAutomobile_ShouldUseSitToStillTransition, CVehicle_GetLayoutInfo, i64_extend8_s; globals 19623876

### CTaskMotionInAutomobile_CheckIfPedWantsToMove (lines 5039929–5040002, 75 lines)

helper; calls CTaskMotionInAutomobile_CheckIfPedWantsToMove, CPed_GetControlFromPlayer, rage_ioValue_GetNorm, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup...; globals 25452388, 8350384, 7737732; 1 vtable call(s); 1 atomic op(s)

### CTaskMotionInAutomobile_ShouldPanic (lines 5040004–5040072, 70 lines)

helper; calls CTaskMotionInAutomobile_ShouldPanic, CVehicle_GetSeatAnimationInfo_1, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1...; globals 10854472, 25451912, 8350384, 25451908; 1 atomic op(s)

### CTaskMotionInAutomobile_IsCloseDoorStateValid (lines 5040074–5040127, 55 lines)

query / predicate; calls CTaskMotionInAutomobile_IsCloseDoorStateValid, CSeatManager_GetPedsSeatIndex, CVehicle_GetDirectEntryPointIndexForPed, CVehicle_IsEntryIndexValid, CVehicle_GetEntryAnimInfo, rage_fwClipSetManager_GetClipSet...; globals 10854472, 15562208; 1 vtable call(s)

### CTaskMotionInAutomobile_CheckForHorn (lines 5040129–5040182, 55 lines)

helper; calls CTaskMotionInAutomobile_CheckForHorn, i64_extend8_s, CVehicle_IsHornOn, CPed_GetControlFromPlayer, rage_ioValue_IsDown; globals 4334628; 1 loop(s)

### CTaskMotionInAutomobile_SetSitIdleMoveNetworkState (lines 5040184–5040198, 16 lines)

setter; calls CTaskMotionInAutomobile_SetSitIdleMoveNetworkState, CMoveNetworkHelperFunctions_SetMoveNetworkState

### CTaskMotionInAutomobile_SetClipPlaybackRate (lines 5040200–5040343, 145 lines)

setter; calls CTaskMotionInAutomobile_SetClipPlaybackRate, CVehicleLayoutInfo_GetAnimRateSet, CVehicle_GetLayoutInfo, CPed_WantsToUseActionMode, CPed_IsUsingStealthMode, CAnimRateSet_sAnimRateTuningPair_GetRate...; globals 25449668, 25444692, 19658944, 19658936...

### CTaskMotionInAutomobile_PickRoadRageAnim (lines 5040345–5040366, 23 lines)

helper; calls CTaskMotionInAutomobile_PickRoadRageAnim, rage_fwClipSetRequestHelper_Release, CVehicle_GetLayoutInfo, i32_trunc_sat_f32_s, rage_fwClipSetRequestHelper_Request; globals 10854472

### CTaskMotionInAutomobile_ProcessPostFSM (lines 5040368–5040371, 5 lines)

processing / event handling; calls CTaskMotionInAutomobile_ProcessPostFSM

### CTaskMotionInAutomobile_ProcessPhysics (lines 5040373–5040547, 176 lines)

processing / event handling; calls CTaskMotionInAutomobile_ProcessPhysics, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25451436, 8350384, 25451432, 25451160...; 1 vtable call(s); 1 atomic op(s)

### CTaskMotionInAutomobile_ProcessImpactReactions (lines 5040549–5041263, 716 lines)

processing / event handling; calls CTaskMotionInAutomobile_ProcessImpactReactions, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25449808, 8350384, 25449804, 28501281...; 2 vtable call(s); 15 atomic op(s)

### CTaskMotionInAutomobile_ProcessPostMovement (lines 5041265–5041302, 39 lines)

processing / event handling; calls CTaskMotionInAutomobile_ProcessPostMovement, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25451440, 8350384, 7737088; 1 atomic op(s)

### CTaskMotionInAutomobile_ProcessDamageFromImpacts (lines 5041304–5041588, 286 lines)

processing / event handling; calls CTaskMotionInAutomobile_ProcessDamageFromImpacts, CCollisionHistory_Reset, CEntity_GetPhysArch, StatId_GetStatId, StatsInterface_GetIntStat, f32_convert_i32_s...; globals 25451108, 12321248, 20388960, 10852776...; 1 vtable call(s); 3 loop(s); 3 atomic op(s)

### CTaskMotionInAutomobile_ShouldUseLowriderLean (lines 5045792–5045915, 125 lines)

helper; calls CTaskMotionInAutomobile_ShouldUseLowriderLean, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25452208, 8350384, 7737593, 10854472...; 3 atomic op(s)

### CTaskMotionInAutomobile_Compute2DBodyBlendSteeringParam (lines 5045917–5046019, 104 lines)

calculation (math/geometry/route); calls CTaskMotionInAutomobile_Compute2DBodyBlendSteeringParam, rage_ioValue_GetNorm, CPed_GetControlFromPlayer, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup...; globals 25452116, 8350384, 25452120, 7737528...; 3 atomic op(s)

### CTaskMotionInAutomobile_ShouldBeAgitated (lines 5046021–5046063, 44 lines)

helper; calls CTaskMotionInAutomobile_ShouldBeAgitated, CVehicle_GetSeatAnimationInfo_1, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1...; globals 10854472, 25451920, 8350384, 25451916; 1 atomic op(s)

### CTaskMotionInAutomobile_HasModifiedLowriderSuspension (lines 5046065–5046135, 72 lines)

query / predicate; calls CTaskMotionInAutomobile_HasModifiedLowriderSuspension, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider, rage_bkBank_UnSetCurrentGroup...; globals 25452252, 8350384, 12321248, 7737604; 1 loop(s); 1 atomic op(s)

### CTaskMotionInAutomobile_CanTransitionToFirstPersonAnims (lines 5046137–5046223, 88 lines)

helper; calls CTaskMotionInAutomobile_CanTransitionToFirstPersonAnims, camCinematicDirector_IsRenderingCinematicCameraInsideVehicle, CPed_IsFirstPersonShooterModeEnabledForPlayer, CPed_GetIsDrivingVehicle, CPed_IsMale, camInterface_FindFollowPed...; globals 19275176, 19235296, 19239148, 28501281...; 1 vtable call(s); 1 atomic op(s)

### CTaskMotionInAutomobile_CanBeDucked (lines 5046225–5046354, 131 lines)

helper; calls CTaskMotionInAutomobile_CanBeDucked, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider, rage_bkBank_UnSetCurrentGroup...; globals 25451924, 8350384, 7737376, 12321248...; 1 vtable call(s); 2 atomic op(s)

### CTaskMotionInAutomobile_ProcessPostCamera (lines 5046356–5046647, 293 lines)

processing / event handling; calls CTaskMotionInAutomobile_ProcessPostCamera, CTaskMotionInAutomobile_UpdateFirstPersonAnimationState, CPed_GetIsDrivingVehicle, CFirstPersonIkHelper_Reset, CPed_IsInFirstPersonVehicleCamera, operator_new...; globals 25451828, 8350384, 25451832, 25451840...; 2 vtable call(s); 6 atomic op(s)

### CTaskMotionInAutomobile_Debug (lines 5046649–5047308, 661 lines)

debug / diagnostics; calls CTaskMotionInAutomobile_Debug, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1, rage_bkBank_UnSetCurrentGroup...; globals 25451644, 8350384, 25451648, 7737224...; 2 vtable call(s); 16 atomic op(s)

### CTaskMotionInAutomobile_GetNMBlendOutClip (lines 5047310–5047327, 19 lines)

query / predicate; calls CTaskMotionInAutomobile_GetNMBlendOutClip, CVehicle_GetSeatAnimationInfo_1; globals 15566744

### CTaskMotionInAutomobile_PlayerShouldBeAgitated (lines 5047329–5047357, 30 lines)

helper; calls CTaskMotionInAutomobile_PlayerShouldBeAgitated, CTaskMotionInAutomobile_ShouldUseLowriderLeanAltClipset, CWanted_CopsAreSearching, CPed_GetIsDrivingVehicle; globals 25451312, 12321248

### cxx_global_array_dtor_5698 (lines 5047359–5047361, 4 lines)

cleanup / shutdown; calls cxx_global_array_dtor_5698, CTuning_CTuning

### CTaskMotionOnBicycle_CheckForWantsToMove (lines 5047363–5047429, 68 lines)

helper; calls CTaskMotionOnBicycle_CheckForWantsToMove, CHandlingData_GetHandlingData, CPed_GetControlFromPlayer, rage_ioValue_GetNorm01, rage_ioValue_IsDown, CVehicle_GetVelocityIncludingReferenceFrame...; globals 4334628, 25452728, 25452740, 19505840; 1 vtable call(s)

### CTaskMotionOnBicycle_WantsToDoSpecialMove (lines 5047431–5047451, 22 lines)

helper; calls CTaskMotionOnBicycle_WantsToDoSpecialMove, CPed_GetControlFromPlayer, rage_ioValue_IsDown; globals 4334628

### CTaskMotionOnBicycle_WantsToTrackStand (lines 5047453–5047482, 31 lines)

helper; calls CTaskMotionOnBicycle_WantsToTrackStand, CVehicle_GetLayoutInfo, CTaskMotionOnBicycle_GetSprintResultFromPed, CPed_GetControlFromPlayer, rage_ioValue_GetNorm01, CTaskMotionOnBicycle_WantsToDoSpecialMove...

### CTaskMotionOnBicycle_GetSprintResultFromPed (lines 5047484–5047532, 50 lines)

query / predicate; calls CTaskMotionOnBicycle_GetSprintResultFromPed, CPlayerInfo_ControlButtonSprint, CPed_GetControlFromPlayer, rage_ioValue_GetNorm01, CVehicle_GetVelocityIncludingReferenceFrame, CBike_IsConsideredStill...; globals 25453200

### CTaskMotionOnBicycle_CheckForStill (lines 5047534–5047590, 58 lines)

helper; calls CTaskMotionOnBicycle_CheckForStill, CVehicle_GetLayoutInfo, CPed_GetControlFromPlayer, CTaskMotionOnBicycle_WantsToDoSpecialMove, CHandlingData_GetHandlingData, CVehicle_GetIsHandBrakePressed...; globals 19505840, 25452740; 1 vtable call(s)

### CTaskMotionOnBicycle_CanTransitionToStill (lines 5047592–5047652, 62 lines)

helper; calls CTaskMotionOnBicycle_CanTransitionToStill, CTaskMotionOnBicycle_WantsToDoSpecialMove, CVehicle_GetLayoutInfo, CHandlingData_GetHandlingData, CTaskMotionOnBicycle_WantsToTrackStand, rage_bkManager_FindBank...; globals 19505840, 25452940, 8350384, 7737808...; 1 vtable call(s); 1 atomic op(s)

### CTaskMotionOnBicycle_PedWantsToStand (lines 5047654–5047750, 98 lines)

helper; calls CTaskMotionOnBicycle_PedWantsToStand, CTaskMotionOnBicycle_GetSprintResultFromPed, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider_2...; globals 25452944, 8350384, 25452856, 25452764...; 1 atomic op(s)

### CTaskMotionOnBicycle_CTaskMotionOnBicycle_1 (lines 5047752–5047781, 31 lines)

constructor / variant; calls CTaskMotionOnBicycle_CTaskMotionOnBicycle_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CTaskMotionBase_CTaskMotionBase_1; globals 12321880; 1 vtable call(s); 1 loop(s)

### CTaskMotionOnBicycle_CTaskMotionOnBicycle_123834 (lines 5047783–5047786, 5 lines)

helper; calls CTaskMotionOnBicycle_CTaskMotionOnBicycle_123834, CTaskMotionOnBicycle_CTaskMotionOnBicycle_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskMotionOnBicycle_CleanUp (lines 5047788–5047807, 21 lines)

cleanup / shutdown; calls CTaskMotionOnBicycle_CleanUp, CMoveObject_SetSecondaryNetwork, rage_fwAnimDirector_GetMove; 1 vtable call(s)

### CTaskMotionOnBicycle_IsPedPedalling (lines 5047809–5047814, 7 lines)

query / predicate; calls CTaskMotionOnBicycle_IsPedPedalling

### CTaskMotionOnBicycle_ProcessPreFSM (lines 5047816–5047924, 110 lines)

pre-FSM setup / signal processing; calls CTaskMotionOnBicycle_ProcessPreFSM, rage_diagLogf2, CVehicle_GetLayoutInfo, CVehicle_GetSeatAnimationInfo_1, CTaskMotionOnBicycle_WantsToTrackStand, CPed_GetControlFromPlayer...; globals 11547139, 12321252, 11547184, 25452948...; 3 vtable call(s); 1 atomic op(s)

### CTaskMotionOnBicycle_SetSeatClipSet (lines 5049135–5049226, 93 lines)

setter; calls CTaskMotionOnBicycle_SetSeatClipSet, CPed_IsInFirstPersonVehicleCamera, camControlHelper_GetViewModeForContext, rage_diagDisplayf, CSeatManager_GetPedsSeatIndex, CVehicle_GetSeatAnimationInfo...; globals 19235296, 12321252, 28501281, 10854472

### CTaskMotionOnBicycle_SetTaskState (lines 5049228–5049255, 29 lines)

setter; calls CTaskMotionOnBicycle_SetTaskState, rage_diagLogf2, rage_aiTask_SetState; globals 11547195, 12321252; 4 vtable call(s)

### CTaskMotionOnBicycle_SetMoveNetworkStates (lines 5049257–5049423, 168 lines)

setter; calls CTaskMotionOnBicycle_SetMoveNetworkStates, rage_atHashStringNamespaceSupport_TryGetString, rage_diagLogf2, rage_mvParameterBuffer_GenerateFreeCapacity, i64_extend_i32_s, i32_wrap_i64; globals 11547195, 12321252; 2 vtable call(s); 8 loop(s)

### CTaskMotionOnBicycle_AreMoveNetworkStatesValid (lines 5049425–5049518, 95 lines)

helper; calls CTaskMotionOnBicycle_AreMoveNetworkStatesValid, rage_diagLogf2, rage_mvParameterBuffer_GenerateFreeCapacity, i64_extend_i32_s; globals 11547195, 12321252, 12321248; 3 vtable call(s)

### CTaskMotionOnBicycle_CheckForRestartingStateDueToCameraSwitch (lines 5049520–5049590, 72 lines)

helper; calls CTaskMotionOnBicycle_CheckForRestartingStateDueToCameraSwitch, rage_diagLogf2, CTaskMotionOnBicycle_ShouldChangeAnimsDueToCameraSwitch; globals 12321248, 11547139, 12321252

### CTaskMotionOnBicycle_CheckForReversingTransition (lines 5049592–5049659, 69 lines)

helper; calls CTaskMotionOnBicycle_CheckForReversingTransition, CTaskMotionOnBicycle_WantsToTrackStand, CTaskMotionOnBicycle_WantsToDoSpecialMove, CVehicle_GetLayoutInfo, CHandlingData_GetHandlingData, CPed_GetControlFromPlayer...; globals 19505840, 25452868, 25452864, 25452860; 1 vtable call(s)

### CTaskMotionOnBicycle_CheckForStandingTransition (lines 5049661–5049735, 76 lines)

helper; calls CTaskMotionOnBicycle_CheckForStandingTransition, CVehicle_GetLayoutInfo, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddToggle_1...; globals 25452976, 8350384, 7737840, 25452856; 1 atomic op(s)

### CTaskMotionOnBicycle_SetClipsForState (lines 5049737–5049803, 68 lines)

setter; calls CTaskMotionOnBicycle_SetClipsForState, rage_fwMoveNetworkInterface_GetClipSetId, f64_promote_f32, rage_diagLogf2, rage_fwClipSetManager_GetClip, CMoveNetworkHelper_SetClip; globals 10854472, 10854468, 25452672, 25452660...

### CTaskMotionOnBicycleController_CTaskMotionOnBicycleController (lines 5049805–5049826, 23 lines)

helper; calls CTaskMotionOnBicycleController_CTaskMotionOnBicycleController, CTaskMotionBase_CTaskMotionBase, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_New, rage_sysCriticalSectionToken_Unlock, rage_fwKnownRefHolder_fwKnownRefHolder; globals 12321880

### CTaskMotionOnBicycle_SetBlendDurationForState (lines 5049828–5049997, 171 lines)

setter; calls CTaskMotionOnBicycle_SetBlendDurationForState, rage_mvParameterBuffer_GenerateFreeCapacity, CPed_GetControlFromPlayer, rage_ioValue_GetNorm, CBike_GetBikeLeanInputs, i64_extend_i32_s; globals 25452636, 25452856, 25452852, 25452640...

### CTaskMotionOnBicycle_CheckForImpactTransition (lines 5049999–5050066, 69 lines)

helper; calls CTaskMotionOnBicycle_CheckForImpactTransition, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider_2, rage_bkBank_UnSetCurrentGroup...; globals 25452980, 8350384, 7737844, 25452984...; 1 vtable call(s); 2 atomic op(s)

### CTaskMotionOnBicycle_ProcessPostFSM (lines 5050068–5050300, 234 lines)

processing / event handling; calls CTaskMotionOnBicycle_ProcessPostFSM, ReportPlayerResetMismatch, CVehicleMetadataMgr_GetVehicleDriveByInfoFromPed, CPed_IsInFirstPersonVehicleCamera, rage_aiTaskTree_FindTaskByTypeActive, CMoveNetworkHelper_SetFlag...; globals 25459992, 25459972; 2 loop(s)

### CTaskMotionOnBicycle_ProcessPostCamera (lines 5052723–5052726, 5 lines)

processing / event handling; calls CTaskMotionOnBicycle_ProcessPostCamera, CTaskMotionOnBicycle_CheckForRestartingStateDueToCameraSwitch

### CTaskMotionOnBicycle_ShouldChangeAnimsDueToCameraSwitch (lines 5052728–5052752, 26 lines)

helper; calls CTaskMotionOnBicycle_ShouldChangeAnimsDueToCameraSwitch, camInterface_FindFollowPed, CPed_IsInFirstPersonVehicleCamera, camControlHelper_GetViewModeForContext, CTaskMotionOnBicycle_SetSeatClipSet; globals 20159720, 19235296

### CTaskMotionOnBicycle_Debug (lines 5052754–5052887, 135 lines)

debug / diagnostics; calls CTaskMotionOnBicycle_Debug, CDebugScene_FocusEntities_Get, f64_promote_f32, rage_grcDebugDraw_AddDebugOutput_1, CVehicle_GetVelocityIncludingReferenceFrame, LoadZero...; globals 20159720, 25453360, 8350384, 7738008...; 1 vtable call(s); 1 atomic op(s)

### CTaskMotionOnBicycle_VisualizeClip (lines 5052889–5053374, 487 lines)

helper; calls CTaskMotionOnBicycle_VisualizeClip, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider_2, rage_bkBank_UnSetCurrentGroup...; globals 25453380, 8350384, 25453384, 7738016...; 4 loop(s); 10 atomic op(s)

### CTaskMotionOnBicycle_VisualizePrepLaunchTags (lines 5053376–5053528, 154 lines)

helper; calls CTaskMotionOnBicycle_VisualizePrepLaunchTags, CClipEventTags_CTagIteratorAttributeValue_rage_crTag_rage_crPropertyAttributeHashString_rage_atNonFi, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider_2...; globals 15569832, 25453424, 8350384, 7738040...; 2 loop(s); 2 atomic op(s)

### CTaskMotionOnBicycle_VisualizeTrackStandTags (lines 5053530–5053682, 154 lines)

helper; calls CTaskMotionOnBicycle_VisualizeTrackStandTags, CClipEventTags_CTagIteratorAttributeValue_rage_crTag_rage_crPropertyAttributeHashString_rage_atNonFi, rage_bkManager_FindBank, rage_bkManager_IsBankThread, GetOrCreateGroup, rage_bkGroup_AddSlider_2...; globals 15569832, 25453432, 8350384, 7738048...; 2 loop(s); 2 atomic op(s)

### CTaskMotionOnBicycle_GetNMBlendOutClip (lines 5053684–5053699, 17 lines)

query / predicate; calls CTaskMotionOnBicycle_GetNMBlendOutClip, CVehicle_GetSeatAnimationInfo_1; globals 15566744

### cxx_global_array_dtor_5798 (lines 5053701–5053703, 4 lines)

cleanup / shutdown; calls cxx_global_array_dtor_5798, CTuning_CTuning

### CTaskMotionOnBicycleController_CTaskMotionOnBicycleController_1 (lines 5053705–5053727, 24 lines)

constructor / variant; calls CTaskMotionOnBicycleController_CTaskMotionOnBicycleController_1, rage_sysCriticalSectionToken_Lock, rage_atPoolBase_Delete, rage_sysCriticalSectionToken_Unlock, CTaskMotionBase_CTaskMotionBase_1; globals 12321880; 1 loop(s)

### CTaskMotionOnBicycleController_CTaskMotionOnBicycleController_123897 (lines 5053729–5053733, 6 lines)

helper; calls CTaskMotionOnBicycleController_CTaskMotionOnBicycleController_123897, CTaskMotionOnBicycleController_CTaskMotionOnBicycleController_1, rage_sysMemPoolAllocator_SafeFree; globals 25408152

### CTaskMotionOnBicycleController_GetNMBlendOutClip (lines 5053735–5053750, 17 lines)

query / predicate; calls CTaskMotionOnBicycleController_GetNMBlendOutClip, CVehicle_GetSeatAnimationInfo_1; globals 15566744

### CTaskMotionOnBicycleController_ProcessPreFSM (lines 5053752–5053761, 11 lines)

pre-FSM setup / signal processing; calls CTaskMotionOnBicycleController_ProcessPreFSM, CVehicle_GetLayoutInfo

### CTaskMotionOnBicycleController_UpdateFSM (lines 5053763–5054473, 712 lines)

FSM state-machine update (per-frame behavior); calls CTaskMotionOnBicycleController_UpdateFSM, CTaskMotionOnBicycle_SetTaskState, CMoveNetworkHelper_GetBoolean, CTaskMotionOnBicycleController_WantsToFreeWheel, CTaskMotionOnBicycleController_SetMoveNetworkStates, rage_mvParameterBuffer_GenerateFreeCapacity...; globals 25453556, 25453668, 25453204, 25453192...; 2 vtable call(s); 2 atomic op(s)
