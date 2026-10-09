"""wgpu device for the native port: Vulkan by default, adapter choice, GPU timestamps, allocation accounting.

``open_device`` must run before anything else imports wgpu adapters: the backend is chosen through the
WGPU_BACKEND_TYPE environment variable (DESIGN §5.3), overridable with ``backend``.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

import numpy as np

__all__ = ["GpuContext", "open_device", "GpuTimer", "AllocationTracker", "peak_rss_bytes", "FORMAT_BYTES",
           "NoAdapter"]

FORMAT_BYTES = {"rgba32float": 16, "rgba16float": 8, "rgba8unorm": 4, "rgba8unorm-srgb": 4, "depth24plus": 4,
                "depth32float": 4, "r32float": 4}
_BACKENDS = {"vulkan": "Vulkan", "d3d12": "D3D12", "metal": "Metal", "opengl": "OpenGL", "gl": "OpenGL"}


class NoAdapter(RuntimeError):
    """No adapter matches the request (the runner reports it as a by-design skip)."""


@dataclass
class AllocationTracker:
    """Bytes of every texture and buffer the runner created (DESIGN §4.3 memory)."""
    texture_bytes: int = 0
    buffer_bytes: int = 0
    items: list = field(default_factory=list)

    def texture(self, label: str, size, fmt: str, layers: int = 1) -> None:
        w, h = int(size[0]), int(size[1])
        d = int(size[2]) if len(size) > 2 else 1
        b = w * h * d * FORMAT_BYTES[fmt]
        self.texture_bytes += b
        self.items.append(("texture", label, b))

    def buffer(self, label: str, nbytes: int) -> None:
        self.buffer_bytes += int(nbytes)
        self.items.append(("buffer", label, int(nbytes)))


def peak_rss_bytes() -> int:
    """Peak resident set size of this process (0 when the platform offers no cheap way to ask)."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]

            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return int(pmc.PeakWorkingSetSize)
            return 0
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(r) if sys.platform == "darwin" else int(r) * 1024
    except Exception:  # noqa: BLE001 - memory is informative only
        return 0


class GpuContext:
    """Adapter + device + bookkeeping. ``create_buffer``/``create_texture`` record allocations."""

    def __init__(self, adapter, device, wgpu_module):
        self.wgpu = wgpu_module
        self.adapter = adapter
        self.device = device
        self.queue = device.queue
        self.info = dict(adapter.info)
        self.features = set(device.features)
        self.timestamps = "timestamp-query" in self.features
        self.alloc = AllocationTracker()
        self.timestamp_period_ns = self._timestamp_period()

    def _timestamp_period(self) -> float:
        """ns per timestamp tick (wgpu-native resolves raw ticks; wgpuQueueGetTimestampPeriod gives the scale)."""
        try:
            from wgpu.backends.wgpu_native import lib
            return float(lib.wgpuQueueGetTimestampPeriod(self.queue._internal))
        except Exception:  # noqa: BLE001
            return 1.0

    def create_buffer(self, label: str, size: int, usage, data: bytes | None = None):
        size = max(4, (int(size) + 3) // 4 * 4)
        self.alloc.buffer(label, size)
        if data is not None:
            buf = self.device.create_buffer(label=label, size=size, usage=usage | self.wgpu.BufferUsage.COPY_DST)
            self.queue.write_buffer(buf, 0, data)
            return buf
        return self.device.create_buffer(label=label, size=size, usage=usage)

    def create_texture(self, label: str, size, fmt: str, usage, dimension: str = "2d"):
        self.alloc.texture(label, size, fmt)
        return self.device.create_texture(label=label, size=tuple(int(s) for s in size), format=fmt, usage=usage,
                                          dimension=dimension)

    def device_block(self) -> dict:
        """The receipt's "device" block (DESIGN §4.3)."""
        i = self.info
        return {"adapter": i.get("device", ""), "backend": i.get("backend_type", ""),
                "adapter_type": i.get("adapter_type", ""), "vendor": i.get("vendor", ""),
                "driver": i.get("description", ""), "vendor_id": i.get("vendor_id"), "device_id": i.get("device_id"),
                "features": sorted(f for f in self.features if f in ("timestamp-query", "float32-filterable")),
                "timestamp_period_ns": self.timestamp_period_ns}


def open_device(backend: str | None = None, adapter: str | None = None, power: str | None = None) -> GpuContext:
    """Pick an adapter (substring match on device/vendor/description, or by power preference) and open a device
    with timestamp-query and float32-filterable when the adapter has them. Raises NoAdapter."""
    want = backend or os.environ.get("WGPU_BACKEND_TYPE") or "Vulkan"
    want = _BACKENDS.get(str(want).lower(), str(want))
    os.environ["WGPU_BACKEND_TYPE"] = want
    import wgpu  # noqa: PLC0415 - backend env var must be set first

    try:
        ads = list(wgpu.gpu.enumerate_adapters_sync())
    except Exception as e:  # noqa: BLE001 - e.g. a backend this platform does not have
        raise NoAdapter(f"cannot enumerate {want} adapters: {type(e).__name__}: {str(e).splitlines()[0][:200]}") from e
    ads = [a for a in ads if str(a.info.get("backend_type", "")).lower() == want.lower()]
    if not ads:
        raise NoAdapter(f"no {want} adapter")
    chosen = None
    if adapter:
        sub = adapter.lower()
        for a in ads:
            hay = " ".join(str(a.info.get(k, "")) for k in ("device", "vendor", "description")).lower()
            if sub in hay:
                chosen = a
                break
        if chosen is None:
            names = ", ".join(str(a.info.get("device")) for a in ads)
            raise NoAdapter(f"no {want} adapter matches {adapter!r} (have: {names})")
    else:
        order = {"high-performance": ("DiscreteGPU", "IntegratedGPU", "VirtualGPU", "CPU", "Unknown"),
                 "low-power": ("IntegratedGPU", "DiscreteGPU", "VirtualGPU", "CPU", "Unknown")}[power or
                                                                                              "high-performance"]
        rank = {t: i for i, t in enumerate(order)}
        chosen = sorted(ads, key=lambda a: rank.get(str(a.info.get("adapter_type")), len(order)))[0]
    feats = [f for f in ("timestamp-query", "float32-filterable") if f in chosen.features]
    device = chosen.request_device_sync(required_features=feats, label="threejs-native")
    return GpuContext(chosen, device, wgpu)


class GpuTimer:
    """Per-pass GPU timestamps (beginning/end of each pass) grouped by category; ``read`` -> {category: ms}."""

    def __init__(self, ctx: GpuContext, capacity: int = 2048):
        self.ctx = ctx
        self.enabled = ctx.timestamps
        self.capacity = capacity
        self.entries: list[tuple[str, int]] = []
        self.dropped = 0  # passes not timed because the query set was full (reported in timing.json)
        if self.enabled:
            wgpu = ctx.wgpu
            self.query_set = ctx.device.create_query_set(type="timestamp", count=capacity)
            self.resolve_buf = ctx.create_buffer("timestamps.resolve", capacity * 8,
                                                 wgpu.BufferUsage.QUERY_RESOLVE | wgpu.BufferUsage.COPY_SRC)

    def reset(self) -> None:
        self.entries = []

    def pass_writes(self, category: str) -> dict | None:
        """timestamp_writes for a render/compute pass, or None when disabled/full."""
        if not self.enabled:
            return None
        if 2 * (len(self.entries) + 1) > self.capacity:
            self.dropped += 1
            return None
        i = 2 * len(self.entries)
        self.entries.append((category, i))
        return {"query_set": self.query_set, "beginning_of_pass_write_index": i, "end_of_pass_write_index": i + 1}

    def resolve(self, encoder) -> None:
        if self.enabled and self.entries:
            encoder.resolve_query_set(self.query_set, 0, 2 * len(self.entries), self.resolve_buf, 0)

    def read(self) -> dict[str, float]:
        """Sum of pass durations per category in ms (call after the encoder holding resolve() was submitted)."""
        if not self.enabled or not self.entries:
            return {}
        n = 2 * len(self.entries)
        raw = np.frombuffer(self.ctx.queue.read_buffer(self.resolve_buf, 0, n * 8), dtype=np.uint64)
        out: dict[str, float] = {}
        for cat, i in self.entries:
            ticks = int(raw[i + 1]) - int(raw[i])
            out[cat] = out.get(cat, 0.0) + max(ticks, 0) * self.ctx.timestamp_period_ns * 1e-6
        return out
