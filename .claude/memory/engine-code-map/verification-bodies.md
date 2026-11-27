# Verification: exact function bodies (2026-11-23)

Programmatically extracted from game.dcmp using the verified index. Each function printed start -> next function definition. This is the evidence behind the "read" claims.


## RageDirect3DDeviceContext11_DrawIndexed — lines 867056..867060 (5 lines)

function RageDirect3DDeviceContext11_DrawIndexed(a:{ a:long, b:long }, b:int, c:int, d:int) { // func10337
  a = a.b;
  call_indirect(a, b, c, d, a.a[12]:long);
}


## rage_fwBaseEntityContainer_SetLodDistCached — lines 565162..565186 (25 lines)

function rage_fwBaseEntityContainer_SetLodDistCached(a:long, b:int, c:int) { // func5720
  var d:int;
  var e:long;
  if (b == 65535) goto B_a;
  d = a[16]:ushort;
  br_table[B_c, B_b, B_a, ..B_d]((d >> 14) - 1);
  label B_d:
  (if ((d & 16383) > b) { a[1]:long + (i64_extend_i32_u(b) << 6L) } else { e })[6]:short =
    c;
  return ;
  label B_c:
  (a[1]:long + (i64_extend_i32_u(b) << 6L))[6]:short = c;
  return ;
  label B_b:
  (a[1]:long + (a = i64_extend_i32_u(d << 2) & 65520L) + a + a + a + a +
   a +
   a +
   ((a = i64_extend_i32_u(d) & 16383L) << 3L) +
   (a = a << 1L) +
   a +
   (i64_extend_i32_u(b) << 1L))[0]:short =
    c;
  label B_a:
}


## EntityDetails_GetLODDist — lines 2409012..2409045 (34 lines)

function EntityDetails_GetLODDist(a:long, b:short_ptr) { // func30042
  var g:float;
  var f:float;
  var h:int;
  var c:int_ptr = stack_pointer - 48L;
  stack_pointer = c;
  if (a != 0L) {
    var d:float_ptr = a[4]:long;
    if (eqz(d)) {
      h = a[84]:ushort;
      goto B_c;
    }
    var e:float = d[15];
    if (
      abs(e - (g = f32_convert_i32_u(h = a[84]:ushort))) <=
      select_if(
        f = select_if(1.0f, f = select_if(-(e), e, e < 0.0f), f < 1.0f),
        g,
        f > g) *
      0.000001f) goto B_c;
    c[4] = h;
    c[5] = i32_trunc_sat_f32_u(e);
    siprintf(c + 32L, 3625564L, c + 16L);
    goto B_b;
    label B_c:
    c[0] = h;
    siprintf(c + 32L, 2236300L, c);
    label B_b:
    b[4] = 0;
    rage_atString_Append(b, c + 32L, i32_wrap_i64(strlen(c + 32L)));
  }
  stack_pointer = c + 48L;
}


## CLodMgr_StartSlodModeCb — lines 3832821..3832832 (12 lines)

function CLodMgr_StartSlodModeCb() { // func47187
  23389032L[0]:byte = 1;
  23389028L[0]:int =
    ((((((23404096L[0]:ubyte | 23404097L[0]:ubyte << 1) |
         23404098L[0]:ubyte << 2) |
        23404099L[0]:ubyte << 3) |
       23404100L[0]:ubyte << 4) |
      23404101L[0]:ubyte << 5) |
     23404102L[0]:ubyte << 6) &
    255;
}


## rage_grcDevice_DrawIndexedPrimitive — lines 857286..857360 (75 lines)

function rage_grcDevice_DrawIndexedPrimitive(a:int, b:int, c:int) { // func10029
  var e:int_ptr;
  if (12483660L[0]:ubyte) { rage_grcStateBlock_DoFlush() }
  rage_grcDevice_SetUpPriorToDraw(a);
  var d:long = (tls_base + 1160L)[0]:long;
  if (12374960L[0]:ubyte == 1) {
    call_indirect(d, c, 12374968L[0]:int, b, 0, 0, (d[0]:long)[20]:long);
    d = tls_base + 1168L;
    e = d[0]:long;
    if (eqz(e)) goto B_b;
    e[0] = (c = 12374968L[0]:int * c) + e[0];
    br_table[B_c, B_m, B_l, B_k, B_j, B_i, B_h, B_g, B_f, ..B_d](a)
    label B_m:
    c = c >> 1;
    goto B_c;
    label B_l:
    c = c - 1;
    goto B_c;
    label B_k:
    c = c / 3;
    goto B_c;
    label B_j:
    c = c - 2;
    goto B_c;
    label B_i:
    c = c - 2;
    goto B_c;
    label B_h:
    c = c >> 2;
    goto B_c;
    label B_g:
    c = c >> 2;
    goto B_c;
    label B_f:
    c = c / 6;
    goto B_c;
  }
  call_indirect(d, c, b, 0, (d[0]:long)[12]:long);
  d = tls_base + 1168L;
  e = d[0]:long;
  if (eqz(e)) goto B_b;
  e[0] = e[0] + c;
  br_table[B_c, B_u, B_t, B_s, B_r, B_q, B_p, B_o, B_n, ..B_d](a)
  label B_u:
  c = c >> 1;
  goto B_c;
  label B_t:
  c = c - 1;
  goto B_c;
  label B_s:
  c = c / 3;
  goto B_c;
  label B_r:
  c = c - 2;
  goto B_c;
  label B_q:
  c = c - 2;
  goto B_c;
  label B_p:
  c = c >> 2;
  goto B_c;
  label B_o:
  c = c >> 2;
  goto B_c;
  label B_n:
  c = c / 6;
  goto B_c;
  label B_d:
  c = 0;
  label B_c:
  d = d[0]:long;
  d[1]:int = d[1]:int + c;
  label B_b:
}


## rage_dlCmdNewDrawList_ExecuteStatic — lines 526848..526880 (33 lines)

function rage_dlCmdNewDrawList_ExecuteStatic(a:int_ptr) { // func4868
  var c:int;
  var e:int_ptr;
  var d:int_ptr = stack_pointer - 16L;
  stack_pointer = d;
  var b:int = a[4];
  if (b < 11054960L[0]:ushort) {
    11012076L[0]:int =
      (b = (c = a[2] & 1) +
           (e = 11054952L[0]:long + (i64_extend_i32_u(b) << 2L))[0]);
    11012076L[0]:int =
      b -
      if (e[0] != b) {
        (e = 11012152L[0]:long)[21118] = e[21118] | -2147483648;
        a[2] & 1;
      } else {
        c
      }
    if (eqz(11062204L[0]:ubyte)) {
      if (11012027L[0]:ubyte >= 6) {
        d[0] = a[1];
        rage_diagLogf2(11012024L, 6, 2147984L, d);
      }
      b = a[1];
      11062204L[0]:byte = 1;
      11062200L[0]:int = b;
    }
    stack_pointer = d + 16L;
    return ;
  }
  unreachable;
}


## rage_dlDrawListMgr_AdjustFragmentLOD — lines 532126..532144 (19 lines)

function rage_dlDrawListMgr_AdjustFragmentLOD(a:int_ptr, b:int_ptr, c:int) { // func5015
  var d:int;
  var f:int_ptr = a + 16L;
  var e:int = b[0];
  if (c) {
    c = a[4];
    c = select_if(c, d = f[8], c > d);
    if (c <= e + 1) goto B_a;
    c = c - 1;
    goto B_b;
  }
  c = a[3];
  c = select_if(c, d = f[7], c > d);
  if (c <= e) goto B_a;
  label B_b:
  b[0] = c;
  label B_a:
}


## rage_fwRenderPhase_DrawListPrologue — lines 548250..548286 (37 lines)

function rage_fwRenderPhase_DrawListPrologue(a:long) { // func5296
  var d:int;
  var b:long = stack_pointer - 16L;
  stack_pointer = b;
  var c:long = 6593728L[0]:long;
  call_indirect(0L,
                rage_dlDrawListMgr_GetDrawListName(a[2]:int),
                1048114L,
                176,
                0,
                a[246]:float,
                0,
                c);
  a = rage_dlCmdNewDrawList_dlCmdNewDrawList(
        rage_dlCmdBase_operator_new(20L),
        a[2]:int);
  a[0]:int = (a[0]:int & -1048576) | 4101;
  a = 11012104L[0]:long;
  a[4218]:int = a[4218]:int + 1;
  let t0 = SimdStoreLane(a, LoadZero(a) i32x4_add V128);
  b[3]:int = 0;
  if (rage_grcDebugDraw_IsExpectingSubRenderThreadDebugDraw(0)) {
    11547040L[0]:int =
      (d = rage_grcDebugDraw_AllocateSubRenderBatcher(0));
    b[2]:int = d;
    rage_DLC_AddInternal_rage_grcDebugDraw_LingerBuffer(b + 12L, b + 8L);
  }
  b[3]:int = 1;
  if (rage_grcDebugDraw_IsExpectingSubRenderThreadDebugDraw(1)) {
    b[2]:int = (d = rage_grcDebugDraw_AllocateSubRenderBatcher(b[3]:int));
    (b[3]:uint << 2L)[2886760]:int = d;
    rage_DLC_AddInternal_rage_grcDebugDraw_LingerBuffer(b + 12L, b + 8L);
  }
  stack_pointer = b + 16L;
  t0;
}


## rage_fwScan_AddCullShape — lines 566756..566761 (6 lines)

function rage_fwScan_AddCullShape():long { // func5760
  var a:int;
  11124760L[0]:short = (a = 11124760L[0]:ushort) + 1;
  return (i64_extend_i32_u(a) & 65535L) * 368L + 11115040L;
}


## rage_fwDrawData_AddToDrawList — lines 522609..522612 (4 lines)

function rage_fwDrawData_AddToDrawList(a:long, b:long, c:long):long { // func4721
  return 0L
}


## CLodScale_SetGlobalScaleFromScript — lines 3843317..3843321 (5 lines)

function CLodScale_SetGlobalScaleFromScript(a:float) { // func47412
  23318984L[0]:float = a;
  23319072L[0]:byte = 23319072L[0]:ubyte | 1;
}


## CLodScale_SetRemappingFromScript — lines 3843373..3843380 (8 lines)

function CLodScale_SetRemappingFromScript(a:float, b:float, c:float, d:float) { // func47415
  23319104L[0]:float = d;
  23319100L[0]:float = c;
  23319096L[0]:float = b;
  23319092L[0]:float = a;
  23319072L[0]:byte = 23319072L[0]:ubyte | 8;
}


## CLodMgr_OverrideLodDist — lines 3843322..3843330 (9 lines)

function CLodMgr_OverrideLodDist(a:long_ptr, b:int) { // func47413
  if (eqz(a)) goto B_a;
  var c:long = a[21];
  if ((c & -72057594037927936L) != 360287970189639680L) goto B_a;
  a[21] = i64_extend_i32_u(b & 65535) | (c & 432345564227502080L);
  call_indirect(a, (a[0])[37]:long);
  label B_a:
}


## streaming_commands_CommandOverrideLodScaleThisFrame — lines 4140792..4140795 (4 lines)

function streaming_commands_CommandOverrideLodScaleThisFrame(a:float) { // func60408
  CLodScale_SetGlobalScaleFromScript(a)
}


## CCutSceneCameraEntity_GetMapLodScale — lines 2365868..2365873 (6 lines)

function CCutSceneCameraEntity_GetMapLodScale(a:long):float { // func29489
  a = a[13]:long;
  if (eqz(a)) { return -1.0f }
  return a[26]:float;
}


## CSettingsManager_GetSettings — lines 4271858..4271875 (18 lines)

function CSettingsManager_GetSettings(a:int_ptr):long { // func64737
  if (25038060L[0]:ubyte) goto B_a;
  var b:int = 12484492L[0]:int;
  if (eqz(b)) goto B_a;
  a[38] =
    {
      2;
      if (b == 1100) goto B_b;
      1;
      if (b == 1010) goto B_b;
      0;
      label B_b:
    }
  25038060L[0]:byte = 1;
  label B_a:
  return a + 8L;
}


## CSettingsManager_ApplySettings — lines 4339931..4340192 (262 lines)

[too large: 262 lines — print header + only relevant lines]

function CSettingsManager_ApplySettings() { // func65672
  var a:int;
  var e:long;
  var b:int;
  var f:long_ptr;
  var c:int;
  var d:int;
  var h:int_ptr = stack_pointer - 560L;
... [body omitted] ...
L4339952:   call_indirect(e, h, (e[0]:long)[8]:long);
L4339974:   6619400L[0]:byte = eqz(a = 19446852L[0]:float <= 0.2f);
L4340009:     loop L_g {
L4340055:       call_indirect(g, (g[0])[2]:long);
L4340057:       call_indirect(0L, 1634211L, 1425297L, 61, 0, 0.04f, 0, 6593728L[0]:long);
L4340059:       call_indirect(g, e + 12L, e + 72L, (g[0])[23]:long);
L4340061:       call_indirect(0L, 0, 6593736L[0]:long);
L4340122:   j = 19446852L[0]:float;

## CTimeCycle_ApplyLodScaleModifiers — lines 5128333..5128392 (60 lines)

function CTimeCycle_ApplyLodScaleModifiers() { // func77611
  var b:ubyte_ptr;
  var a:int_ptr = stack_pointer - 16L;
  stack_pointer = a;
  b = 19339168L[0]:long;
  if (eqz(b)) goto B_b;
  if (18581244L[0]:int == 2) {
    if (eqz(CReplayMgrInternal_IsPlaybackFlagSet(4))) goto B_b;
    goto B_a;
  }
  if (b[5900]) goto B_a;
  label B_b:
  if (23985088L[0]:long != 0L) { if ((23985096L[0]:int & 34) == 2) goto B_a }
  if (AtomicLoad(19448416L) & 1) goto B_e;
  if (eqz(cxa_guard_acquire(19448416L))) goto B_e;
  CSettingsManager_CSettingsManager_1();
  cxa_atexit(77049L);
  cxa_guard_release(19448416L);
  label B_e:
  if (
    eqz(CSettingsManager_GetSettings(19446816L)[7]:float < 1.0f)) goto B_f;
  a[3] = -781875541;
  rage_atHashStringNamespaceSupport_AddString(0, -781875541, 942836L);
  b = rage_tcManager_FindModifier(25492320L, a + 12L);
  if (eqz(b)) goto B_f;
  if (AtomicLoad(19448416L) & 1) goto B_g;
  if (eqz(cxa_guard_acquire(19448416L))) goto B_g;
  CSettingsManager_CSettingsManager_1();
  cxa_atexit(77049L);
  cxa_guard_release(19448416L);
  label B_g:
  rage_tcModifier_Apply(
    b,
    1.0f - CSettingsManager_GetSettings(19446816L)[7]:float);
  label B_f:
  if (AtomicLoad(19448416L) & 1) goto B_h;
  if (eqz(cxa_guard_acquire(19448416L))) goto B_h;
  CSettingsManager_CSettingsManager_1();
  cxa_atexit(77049L);
  cxa_guard_release(19448416L);
  label B_h:
  if (
    eqz(CSettingsManager_GetSettings(19446816L)[39]:float > 0.0f)) goto B_a;
  a[2] = 1707374559;
  rage_atHashStringNamespaceSupport_AddString(0, 1707374559, 942833L);
  b = rage_tcManager_FindModifier(25492320L, a + 8L);
  if (eqz(b)) goto B_a;
  if (AtomicLoad(19448416L) & 1) goto B_i;
  if (eqz(cxa_guard_acquire(19448416L))) goto B_i;
  CSettingsManager_CSettingsManager_1();
  cxa_atexit(77049L);
  cxa_guard_release(19448416L);
  label B_i:
  rage_tcModifier_Apply(
    b,
    CSettingsManager_GetSettings(19446816L)[39]:float);
  label B_a:
  stack_pointer = a + 16L;
}


## rage_grcBegin — lines 817371..817395 (25 lines)

function rage_grcBegin(a:int, b:int) { // func9561
  var c:long = stack_pointer - 16L;
  stack_pointer = c;
  var d:long_ptr = (tls_base + 1136L)[0]:long;
  if (d != 0L) {
    d[16] =
      rage_grcBatcher_Reserve(d,
                              (a << 8 | b << 11) | 4,
                              i64_extend_i32_s(b) * 36L);
    goto B_a;
  }
  if (eqz(12432424L[0]:long | 12432384L[0]:long)) {
    rage_grcEffect_Bind(
      12382200L[0]:long,
      select_if(12623068L, 12623072L, 12374352L[0]:ubyte & 1)[0]:int)
  }
  12623360L[0]:long = 12623096L[0]:long;
  12484536L[0]:long =
    rage_grcDevice_BeginIndexedVertices(a, b, 36, c + 8L, 0);
  12484544L[0]:int = 0;
  12484548L[0]:int = b;
  label B_a:
  stack_pointer = c + 16L;
}


## rage_grcVertex — lines 817396..817433 (38 lines)

function rage_grcVertex(a:float, b:float, c:float, d:float, e:float, f:float, g:int, h:float, i:float) { // func9562
  var j:{ a:float, b:float, c:float, d:float, e:float, f:float, g:int, h:float, i:float }
  var k:long_ptr = (tls_base + 1136L)[0]:long;
  if (k != 0L) {
    j = k[16];
    if (eqz(j)) goto B_a;
    k[16] = j + 36L;
    j.i = i;
    j.h = h;
    j.g = g;
    j.f = f;
    j.e = e;
    j.d = d;
    j.c = c;
    j.b = b;
    j.a = a;
    return ;
  }
  j = 12484536L[0]:long;
  if (eqz(12484548L[0]:int)) goto B_c;
  if (j != 0L) goto B_c;
  12484544L[0]:int = 12484544L[0]:int + 1;
  return ;
  label B_c:
  12484536L[0]:long = j + 36L;
  12484544L[0]:int = 12484544L[0]:int + 1;
  j.a = a;
  j.b = b;
  j.c = c;
  j.d = d;
  j.e = e;
  j.f = f;
  j.g = (g << 16 & 16711680) | ((g >> 16 & 255) | (g & -16711936));
  j.h = h;
  j.i = i;
  label B_a:
}


## rage_grcEnd — lines 817434..817461 (28 lines)

function rage_grcEnd() { // func9563
  var a:long_ptr = (tls_base + 1136L)[0]:long;
  if (a != 0L) {
    a[16] = 0L;
    return ;
  }
  a = 12484536L[0]:long;
  if (12374960L[0]:ubyte == 1) {
    if (a != 0L) {
      12484464L[0]:long = 0L;
      a = (tls_base + 1160L)[0]:long;
      call_indirect(a, 12624440L[0]:long, 0, (a[0])[15]:long);
      rage_grcDevice_DrawInstancedVertices();
      12484536L[0]:long = 0L;
    }
    12484548L[0]:int = 0;
    return ;
  }
  if (a != 0L) {
    12484464L[0]:long = 0L;
    a = (tls_base + 1160L)[0]:long;
    call_indirect(a, 12624440L[0]:long, 0, (a[0])[15]:long);
    rage_grcDevice_DrawVertices();
    12484536L[0]:long = 0L;
  }
  12484548L[0]:int = 0;
}


## rage_grcDevice_DrawVertices — lines 815973..816004 (32 lines)

function rage_grcDevice_DrawVertices() { // func9548
  var b:long_ptr;
  if (eqz(12631108L[0]:int)) goto B_a;
  var a:long = tls_base + 1160L;
  var c:int = 12631104L[0]:int;
  if (c == 5) {
    12631104L[0]:int = 3;
    b = a[0]:long;
    call_indirect(b, 12624456L[0]:long, 57, 0, (b[0])[19]:long);
    rage_grcDevice_SetUpPriorToDraw(12631104L[0]:int);
    a = a[0]:long;
    call_indirect(a, 12631108L[0]:int * 3 - 6, 0, 0, (a[0]:long)[12]:long);
    b = tls_base + 1168L;
    a = b[0];
    if (eqz(a)) goto B_a;
    a[0]:int = a[0]:int + (c = 12631108L[0]:int) * 3 - 6;
    a = b[0];
    a[1]:int = c + a[1]:int - 2;
    return ;
  }
  rage_grcDevice_SetUpPriorToDraw(c);
  a = a[0]:long;
  call_indirect(a, 12631108L[0]:int, 0, (a[0]:long)[13]:long);
  b = tls_base + 1168L;
  a = b[0];
  if (eqz(a)) goto B_a;
  a[0]:int = (c = 12631108L[0]:int) + a[0]:int;
  a = b[0];
  a[1]:int = c + a[1]:int;
  label B_a:
}


## rage_grcBatcher_Reserve — lines 816964..817082 (119 lines)

function rage_grcBatcher_Reserve(a:long, b:int, c:long):long { // func9556
  var e:long;
  var i:int;
  var f:{ a:int, b:int, c:int, d:int, e:long, f:long } =
    stack_pointer - 32L;
  stack_pointer = f;
  var h:{ a:simd, b:long } = a[12]:long;
  var d:long = h - (e = a[10]:long) >> 2L;
  i = a[26]:int;
  br_table[B_d, B_e, B_e, B_e, B_d, ..B_e](i - 1);
  label B_e:
  if (i - 7 > 1) goto B_c;
  goto B_b;
  label B_d:
  d = d - 4L;
  label B_c:
  var g:long = c >> 2L;
  if (g < d) {
    e[0]:int = b;
    a[11]:long = (d = (c = a[10]:long) + 4L);
    a[10]:long = c + (g << 2L) + 4L;
    goto B_a;
  }
  br_table[B_l, B_h, B_b, B_m, B_b, B_i, B_n, ..B_b](i)
  label B_n:
  if (eqz(call_indirect(f + 24L, f + 16L, a[14]:long))) goto B_b;
  c = f.e;
  d = f.f;
  if (a[10]:long != 0L) {
    e = a[9]:long;
    e[1]:long@4 = d;
    e[0]:int = 2;
    (a[10]:long)[0]:int = 0;
    (a[10]:long)[1]:long@4 = d;
    goto B_o;
  }
  a[8]:long = d;
  label B_o:
  a[9]:long = d;
  a[12]:long = d + (c & -4L) - 12L;
  d[1]:long@4 = 0L;
  d[0]:int = 2;
  a[10]:long = d + 12L;
  d[3]:int = b;
  a[11]:long = (d = (c = a[10]:long) + 4L);
  a[10]:long = c + (g << 2L) + 4L;
  goto B_a;
  label B_m:
  if (eqz(12374976L[0]:long)) goto B_k;
  if (eqz(a[145]:ubyte)) {
    if (e != 0L) {
      a[10]:long = e + 4L;
      e[0]:int = 1;
    }
    a[145]:byte = 1;
  }
  d = tls_base + 1136L;
  e = d[0]:long;
  d[0]:long = 0L;
  rage_grcBatcher_RenderInternal(a);
  d[0]:long = e;
  if (a[26]:int == 6) {
    h = a - -64L;
    d = a[8]:long;
    if (d != 0L) {
      g = a[15]:long;
      loop L_v {
        e = d[1]:long@4;
        call_indirect(d, g);
        d = e;
        if (d != 0L) continue L_v;
      }
    }
    a[12]:long = 0L;
    h.b = 0L;
    h.a = V128;
    goto B_s;
  }
  a[10]:long = a[9]:long;
  label B_s:
  a[145]:byte = 0;
  goto B_j;
  label B_l:
  f.d = h - (a = a[9]:long);
  f.c = e - a;
  f.b = i32_wrap_i64(d) << 2;
  f.a = i32_wrap_i64(g) << 2;
  Quitf(3951172L, f);
  goto B_g;
  label B_k:
  a[145]:byte = 0;
  a[10]:long = a[9]:long;
  label B_j:
  a[26]:int = 0;
  a[11]:long = 0L;
  d = rage_grcBatcher_Reserve(a, b, c);
  a[26]:int = 3;
  goto B_a;
  label B_i:
  a[10]:long = e + 4L;
  e[0]:int = 34;
  a[26]:int = 8;
  goto B_g;
  label B_h:
  a[10]:long = e + 4L;
  e[0]:int = 33;
  a[26]:int = 7;
  goto B_b;
  label B_g:
  d = 0L;
  goto B_a;
  label B_b:
  d = 0L;
  a[11]:long = 0L;
  label B_a:
  stack_pointer = f + 32L;
  return d;
}


## rage_grcBatcher_RenderInternal — lines 830958..833133 (2176 lines)

[too large: 2176 lines — print header + only relevant lines]

function rage_grcBatcher_RenderInternal(a:long_ptr) { // func9732
  var d:long;
  var f:long;
  var z:int;
  var ba:int;
  var ea:int;
  var l:long;
  var m:float_ptr;
... [body omitted] ...
L831011:   loop L_b {
L831035:     call_indirect(b, f = c[3]:long@4, a, c[1]:long@4);
L831042:     aa = 12484544L[0]:int;
L831043:     loop L_cb {
L831072:       12484544L[0]:int = (aa = aa + 1);
L831075:       12484544L[0]:int = (aa = aa + 1);
L831103:         call_indirect(d, 12624440L[0]:long, 0, (d[0]:long)[15]:long);
L831104:         rage_grcDevice_DrawInstancedVertices();
L831114:       call_indirect(d, 12624440L[0]:long, 0, (d[0]:long)[15]:long);
L831115:       rage_grcDevice_DrawVertices();
L831147:     call_indirect(e - -64L, 6634312L[0]:long);
L831182:     call_indirect(e - -64L, 6634312L[0]:long);
L831270:     rage_grcDrawLine(e - -64L, e + 48L, c[9]:int);
L831276:     rage_grcDrawLine_1(e - -64L, e + 48L, c[9]:int, c[10]:int);
L831293:     rage_grcDraw2dQuad(e - -64L, e + 48L, e + 32L, e + 16L, z);
L831325:     loop L_xb {
L831360:     loop L_ac {
L831373:     rage_grcDrawBox(e + 48L, e - -64L, c[21]:int);
L831382:     rage_grcDrawSolidBox(e + 48L, e - -64L, c[21]:int);
L831390:     rage_grcDrawFrustum(e - -64L,
L831404:     rage_grcDrawEllipsoid(e + 48L,
L831468:       ba = 12484544L[0]:int;
L831469:       loop L_ic {
L831497:         12484544L[0]:int = (ba = ba + 1);
L831500:         12484544L[0]:int = (ba = ba + 1);
L831527:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L831528:         rage_grcDevice_DrawInstancedVertices();
L831537:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L831538:       rage_grcDevice_DrawVertices();
L831554:       ba = 12484544L[0]:int;
L831556:       loop L_sc {
L831584:         12484544L[0]:int = (ba = ba + 1);
L831587:         12484544L[0]:int = (ba = ba + 1);
L831614:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L831615:         rage_grcDevice_DrawInstancedVertices();
L831624:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L831625:       rage_grcDevice_DrawVertices();
L831641:       ba = 12484544L[0]:int;
L831643:       loop L_cd {
L831671:         12484544L[0]:int = (ba = ba + 1);
L831674:         12484544L[0]:int = (ba = ba + 1);
L831701:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L831702:         rage_grcDevice_DrawInstancedVertices();
L831711:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L831712:       rage_grcDevice_DrawVertices();
L831726:     rage_grcDrawPartialSphere(e - -64L,
L831738:     rage_grcDrawSpiral(e - -64L,
L831754:     rage_grcDrawCircle(pa,
L831769:     rage_grcDrawArc(pa,
L831787:     rage_grcDrawCapsule(ra, pa, e - -64L, c[20]:int, c[21]:int != 0, c[22]:float);
L831903:       call_indirect(f, 6634312L[0]:long)
L831929:       loop L_ae {
L831945:         z = 12484544L[0]:int;
L831947:         loop L_be {
L831986:           12484544L[0]:int = (z = z + 1);
L831989:           12484544L[0]:int = (z = z + 1);
L832030:           12484544L[0]:int = (z = z + 1);
L832033:           12484544L[0]:int = (z = z + 1);
L832058:           call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832059:           rage_grcDevice_DrawInstancedVertices();
L832065:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832066:         rage_grcDevice_DrawVertices();
L832087:       z = 12484544L[0]:int;
L832089:       loop L_qe {
L832117:         12484544L[0]:int = (z = z + 1);
L832120:         12484544L[0]:int = (z = z + 1);
L832147:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832148:         rage_grcDevice_DrawInstancedVertices();
L832157:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832158:       rage_grcDevice_DrawVertices();
L832176:       ca = 12484544L[0]:int;
L832177:       loop L_af {
L832205:         12484544L[0]:int = (ca = ca + 1);
L832208:         12484544L[0]:int = (ca = ca + 1);
L832234:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832235:         rage_grcDevice_DrawInstancedVertices();
L832244:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832245:       rage_grcDevice_DrawVertices();
L832261:       ca = 12484544L[0]:int;
L832263:       loop L_kf {
L832291:         12484544L[0]:int = (ca = ca + 1);
L832294:         12484544L[0]:int = (ca = ca + 1);
L832320:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832321:         rage_grcDevice_DrawInstancedVertices();
L832330:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832331:       rage_grcDevice_DrawVertices();
L832347:       ca = 12484544L[0]:int;
L832349:       loop L_uf {
L832377:         12484544L[0]:int = (ca = ca + 1);
L832380:         12484544L[0]:int = (ca = ca + 1);
L832406:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832407:         rage_grcDevice_DrawInstancedVertices();
L832416:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832417:       rage_grcDevice_DrawVertices();
L832435:       ca = 12484544L[0]:int;
L832436:       loop L_eg {
L832464:         12484544L[0]:int = (ca = ca + 1);
L832467:         12484544L[0]:int = (ca = ca + 1);
L832493:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832494:         rage_grcDevice_DrawInstancedVertices();
L832503:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832504:       rage_grcDevice_DrawVertices();
L832520:       z = 12484544L[0]:int;
L832522:       loop L_og {
L832550:         12484544L[0]:int = (z = z + 1);
L832553:         12484544L[0]:int = (z = z + 1);
L832580:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832581:         rage_grcDevice_DrawInstancedVertices();
L832590:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832591:       rage_grcDevice_DrawVertices();
L832609:     loop L_xg {
L832623:       12484544L[0]:int = 0;
L832653:       12484544L[0]:int = 12484544L[0]:int + 1;
L832657:       12484544L[0]:int = 12484544L[0]:int + 1;
L832696:       12484544L[0]:int = 12484544L[0]:int + 1;
L832700:       12484544L[0]:int = 12484544L[0]:int + 1;
L832722:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832723:         rage_grcDevice_DrawInstancedVertices();
L832729:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832730:       rage_grcDevice_DrawVertices();
L832758:       z = 12484544L[0]:int;
L832759:       loop L_nh {
L832787:         12484544L[0]:int = (z = z + 1);
L832790:         12484544L[0]:int = (z = z + 1);
L832830:         12484544L[0]:int = (z = z + 1);
L832833:         12484544L[0]:int = (z = z + 1);
L832860:         call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832861:         rage_grcDevice_DrawInstancedVertices();
L832870:       call_indirect(b, 12624440L[0]:long, 0, (b[0]:long)[15]:long);
L832871:       rage_grcDevice_DrawVertices();
L832887:     rage_grcDrawCylinder(ra, pa, e - -64L, c[20]:int, c[21]:int != 0);
L832896:     rage_grcDrawAxis(pa, e - -64L, c[18]:int != 0);
L832921:     loop L_ai {
L832954:       loop L_ei {
L832970:     rage_grcDrawTexturedPolygon(l, z, ba, j, f);
L832993:       loop L_ii {
L833009:     rage_grcDrawPolygon(l, z, f);
L833033:       loop L_mi {
L833052:     rage_grcDrawTexturedPolygon_1(l, z, h, k, i);
L833058:       (i64_extend_i32_s(call_indirect(f, (f[0]:long)[3]:long)) & -4L) + f;
L833062:       z = call_indirect(f, d[3]:long);
L833079:     call_indirect(f, d[2]:long);
L833091:     loop L_qi {
L833099:     rage_grcDrawPolygon_1(l, z, 1, ba);
L833105:     loop L_ri {
L833112:     rage_grcDrawLabel(e - -64L, ca, aa, l, ba != 0, ra, pa);
L833118:     loop L_si {
L833125:     rage_grcDraw2dText(ka, ja, l, ba != 0, ra, pa, k);

## rage_fwScanNodes_ProcessEntityContainer — lines 574286..574341 (56 lines)

function rage_fwScanNodes_ProcessEntityContainer(a:long, b:long, c:long, d:int) { // func5790
  var e:int;
  if (11526512L[0]:ubyte == 1) { if (11526520L[0]:long == b) goto B_a }
  if (b[16]:ubyte == 1) { if (eqz(b[17]:ubyte & 4)) goto B_c }
  var g:int =
    (a[394]:long +
     (i64_extend16_s(i64_extend_i32_u(e = b[9]:ushort)) << 2L))[0]:int;
  if (eqz(g)) goto B_c;
  var h:int = c[16]:ushort;
  var f:int = h & 16383;
  if (eqz(f)) goto B_c;
  var i:int = i32_extend16_s(h);
  if ((i & -16384) == 16384) {
    f = c[17]:ushort;
    if (eqz(f)) goto B_c;
  }
  e = i32_extend16_s(e - 1150);
  h = select_if(e, 0, e > 0);
  g =
    (g & 16777215) | select_if((d = d << 24) | 134217728, d, i < -16384);
  d = 0;
  loop L_f {
    var j:long = c[1]:long;
    AtomicRmw(0L, 1);
    b = AtomicLoad(6621384L);
    a[829]:int = (e = a[829]:int) + 1;
    b = b + i64_extend_i32_u(e) * 160L;
    b[5]:simd = V128;
    b[13]:long = 282016142589952L;
    b[12]:long = 4373L;
    b[73]:short = 3;
    b[2]:long = 11167424L;
    b[1]:long = 11114752L;
    b[3]:long = a[392]:long;
    var k:long = a[393]:long;
    b[5]:long = j + (i64_extend_i32_s(d) << 6L);
    b[4]:long = k;
    j = (a[389]:long)[1275]:long;
    b[34]:int = 384;
    b[33]:int = (e = select_if(320, f, f >= 320)) << 6;
    b[32]:int = 38080;
    b[7]:simd = V128;
    b[16]:int = h;
    b[14]:int = g;
    b[6]:long = j;
    rage_sysDependencyScheduler_InsertInternal(b);
    d = d + e;
    f = f - e;
    if (f) continue L_f;
  }
  label B_c:
  return ;
  label B_a:
  unreachable;
}


## CSettingsManager_GetSafeModeSettings — lines 4338140..4338177 (38 lines)

function CSettingsManager_GetSafeModeSettings(a:long) { // func65644
  a[72]:int = 0;
  a[35]:long = 0L;
  a[28]:long = 5058224L;
  a[26]:long = 5058136L;
  a[21]:long = 5058048L;
  a[2]:long = 5057920L;
  a[0]:long = 4822872L;
  a[3]:simd@8 = V128;
  a[40]:int = 0;
  a[152]:byte = 0;
  a[37]:int = 0;
  a[10]:int = 1;
  a[11]:long@4 = 0L;
  a[13]:simd@4 = V128;
  a[17]:simd@4 = V128;
  a[21]:simd@4 = V128;
  a[50]:short = 0;
  a[33]:int = 0;
  a[62]:short = 256;
  a[30]:int = 1065185444;
  a[14]:long = 4567730886097638523L;
  a[108]:byte = 0;
  a[26]:int = 1065353216;
  a[63]:int@2 = 0;
  a[36]:int = 2;
  a[22]:simd@8 = V128;
  a[29]:simd@8 = V128;
  a[31]:simd@8 = V128;
  a[17]:long = 4561245704521829581L;
  a[33]:long = 4575657222445255885L;
  a[34]:long = 1L;
  a[216]:byte = 0;
  a[39]:int = 0;
  a[153]:byte = 0;
  a[3]:int = 3;
}


## rage_grcDrawSingleQuadf — lines 815800..815880 (81 lines)

function rage_grcDrawSingleQuadf(a:float, b:float, c:float, d:float, e:float, f:float, g:float, h:float, i:float, j:long) { // func9544
  var k:int;
  var l:long_ptr;
  var n:long = stack_pointer - 16L;
  stack_pointer = n;
  var m:int_ptr = tls_base + 1084L;
  m[0] = (k = m[0]) + 1;
  if (k) {
    l = tls_base + 1088L;
    goto B_a;
  }
  12623360L[0]:long = 12382088L[0]:long;
  if (eqz(12432424L[0]:long | 12432384L[0]:long)) {
    rage_grcEffect_Bind(12382200L[0]:long, 12623072L[0]:int)
  }
  l = tls_base + 1088L;
  l[0] = rage_grcDevice_BeginIndexedVertices(3, 6, 36, n + 8L, 0);
  label B_a:
  k = j[0]:int;
  j = l[0];
  j[8]:float = g;
  j[7]:float = f;
  j[2]:float = e;
  j[1]:float = b;
  j[0]:float = a;
  j[5]:int = 0;
  j[17]:float = i;
  j[16]:float = f;
  j[11]:float = e;
  j[10]:float = d;
  j[9]:float = a;
  j[3]:long@4 = 0L;
  j[14]:int = 0;
  j[26]:float = g;
  j[25]:float = h;
  j[20]:float = e;
  j[19]:float = b;
  j[18]:float = c;
  j[12]:long@4 = 0L;
  j[6]:int =
    (k = (k << 16 & 16711680) | ((k >> 16 & 255) | (k & -16711936)));
  j[15]:int = k;
  j[24]:int = k;
  j[27]:float = a;
  j[22]:long@4 = 0L;
  j[28]:float = d;
  j[29]:float = e;
  j[33]:int = k;
  j[34]:float = f;
  j[35]:float = i;
  j[21]:int = 0;
  j[31]:long@4 = 0L;
  j[36]:float = c;
  j[37]:float = d;
  j[38]:float = e;
  j[42]:int = k;
  j[43]:float = h;
  j[44]:float = i;
  j[30]:int = 0;
  j[40]:long@4 = 0L;
  j[45]:float = c;
  j[46]:float = b;
  j[47]:float = e;
  j[51]:int = k;
  j[52]:float = h;
  j[53]:float = g;
  j[39]:int = 0;
  j[50]:int = 0;
  j[48]:long@4 = 0L;
  l[0] = l[0] + 216L;
  m[0] = (k = m[0] - 1);
  if (eqz(k)) {
    12484464L[0]:long = 0L;
    j = (tls_base + 1160L)[0]:long;
    call_indirect(j, 12624440L[0]:long, 0, (j[0]:long)[15]:long);
    rage_grcDevice_DrawVertices();
    l[0] = 0L;
  }
  stack_pointer = n + 16L;
}


## rage_dlCmdEndDraw_ExecuteStatic — lines 526945..526949 (5 lines)

function rage_dlCmdEndDraw_ExecuteStatic(a:{ a:long, b:long }) { // func4873
  a = a.b;
  call_indirect(a, a.a[8]:long);
}
