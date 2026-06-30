import { useState, useEffect } from 'react'
import { Monitor, Wifi, WifiOff, Activity, Cpu, Radio, Video } from 'lucide-react'
import type { Camera, SystemStatus, MQTTConfig, MQTTStatus, Go2RTCConfig } from '../types'
import { getCameras, getStatus, getMQTTConfig, updateMQTTConfig, getMQTTStatus, getGo2RTCConfig, updateGo2RTCConfig, getModelConfig, updateModelConfig } from '../api'
import type { ModelConfig } from '../api'

export default function System() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [mqttConfig, setMqttConfig] = useState<MQTTConfig>({
    host: '', port: 1883, username: '', password: '', topic: 'behavior-detection/events',
    enabled: false, update_interval: 30, tls_enabled: false, tls_insecure: false,
  })
  const [mqttStatus, setMqttStatus] = useState<MQTTStatus>({ connected: false, active_sessions: 0 })
  const [mqttSaving, setMqttSaving] = useState(false)
  const [mqttError, setMqttError] = useState<string | null>(null)
  const [go2rtcConfig, setGo2rtcConfig] = useState<Go2RTCConfig>({ webrtc_candidates: '' })
  const [go2rtcSaving, setGo2rtcSaving] = useState(false)
  const [modelConfig, setModelConfig] = useState<ModelConfig>({ detector_path: '', confidence: 0.5, pose_path: '', pose_confidence: 0.3, tracker_config: 'bytetrack.yaml' })
  const [modelSaving, setModelSaving] = useState(false)

  useEffect(() => {
    let cancelled = false

    Promise.all([getCameras(), getStatus(), getMQTTConfig(), getMQTTStatus(), getGo2RTCConfig(), getModelConfig()])
      .then(([camerasData, statusData, mqttCfg, mqttSts, go2rtcCfg, modelCfg]) => {
        if (!cancelled) {
          setCameras(camerasData)
          setStatus(statusData)
          setMqttConfig(mqttCfg)
          setMqttStatus(mqttSts)
          setGo2rtcConfig(go2rtcCfg)
          setModelConfig(modelCfg)
        }
      })
      .catch(() => {
        // silently handle — page will show zeros
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  // ── Derived stats ──
  const totalCameras = cameras.length
  const onlineCount = cameras.filter((c) => c.online !== false).length
  const offlineCount = totalCameras - onlineCount
  const todayEvents = status?.total_events ?? 0

  // ── Helper: get enabled rule names for a camera ──
  function getEnabledRules(camera: Camera): string {
    if (!camera.rules) return '—'
    const names: string[] = []
    if (camera.rules.crowd?.enabled) names.push('Crowd')
    if (camera.rules.fight?.enabled) names.push('Fight')
    if (camera.rules.fall?.enabled) names.push('Fall')
    return names.length > 0 ? names.join(' · ') : '—'
  }

  const handleMqttSave = async () => {
    setMqttSaving(true)
    setMqttError(null)
    try {
      const updated = await updateMQTTConfig(mqttConfig)
      setMqttConfig(updated)
      // Wait briefly for MQTT async connection to establish before checking status
      await new Promise((r) => setTimeout(r, 1000))
      const sts = await getMQTTStatus()
      setMqttStatus(sts)
    } catch (e: unknown) {
      setMqttError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setMqttSaving(false)
    }
  }

  const handleGo2rtcSave = async () => {
    setGo2rtcSaving(true)
    try {
      const updated = await updateGo2RTCConfig(go2rtcConfig)
      setGo2rtcConfig(updated)
    } catch {
      // silently handle
    } finally {
      setGo2rtcSaving(false)
    }
  }

  const handleModelSave = async () => {
    setModelSaving(true)
    try {
      const updated = await updateModelConfig(modelConfig)
      setModelConfig(updated)
    } catch {
      // silently handle
    } finally {
      setModelSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-t3 text-sm">
        Loading...
      </div>
    )
  }

  return (
    <div>
      {/* ── Stat Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 mb-5">
        {/* Total Cameras — blue */}
        <div className="p-3.5 rounded-lg bg-bg2 border border-border">
          <div className="flex items-center gap-1.5 text-[10px] text-t3 uppercase tracking-wide mb-1.5">
            <Monitor size={12} />
            Total Cameras
          </div>
          <div className="font-mono text-[26px] font-semibold text-blue">
            {totalCameras}
          </div>
        </div>

        {/* Online — green */}
        <div className="p-3.5 rounded-lg bg-bg2 border border-border">
          <div className="flex items-center gap-1.5 text-[10px] text-t3 uppercase tracking-wide mb-1.5">
            <Wifi size={12} />
            Online
          </div>
          <div className="font-mono text-[26px] font-semibold text-green">
            {onlineCount}
          </div>
        </div>

        {/* Offline — red */}
        <div className="p-3.5 rounded-lg bg-bg2 border border-border">
          <div className="flex items-center gap-1.5 text-[10px] text-t3 uppercase tracking-wide mb-1.5">
            <WifiOff size={12} />
            Offline
          </div>
          <div className="font-mono text-[26px] font-semibold text-red">
            {offlineCount}
          </div>
        </div>

        {/* Events Today — orange */}
        <div className="p-3.5 rounded-lg bg-bg2 border border-border">
          <div className="flex items-center gap-1.5 text-[10px] text-t3 uppercase tracking-wide mb-1.5">
            <Activity size={12} />
            Events Today
          </div>
          <div className="font-mono text-[26px] font-semibold text-orange">
            {todayEvents}
          </div>
        </div>
      </div>

      {/* ── Camera Status Table ── */}
      {cameras.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-t3 text-sm gap-3">
          <Cpu size={36} strokeWidth={1.5} />
          <span>No camera data</span>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs bg-bg2 rounded-lg border border-border border-separate border-spacing-0 overflow-hidden">
            <thead>
              <tr>
                <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wide bg-card">
                  Camera ID
                </th>
                <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wide bg-card">
                  Name
                </th>
                <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wide bg-card">
                  Status
                </th>
                <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wide bg-card">
                  FPS
                </th>
                <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wide bg-card">
                  Events
                </th>
                <th className="text-left px-3.5 py-2 text-[10px] font-semibold text-t3 uppercase tracking-wide bg-card">
                  Rules Active
                </th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((camera) => {
                const isOnline = camera.online !== false
                return (
                  <tr
                    key={camera.id}
                    className="transition-colors duration-150 hover:bg-card cursor-pointer"
                  >
                    <td className="px-3.5 py-2.5 border-t border-border text-t2 font-mono">
                      {camera.id}
                    </td>
                    <td className="px-3.5 py-2.5 border-t border-border text-t2">
                      {camera.name}
                    </td>
                    <td className="px-3.5 py-2.5 border-t border-border">
                      {isOnline ? (
                        <span className="text-green">● Online</span>
                      ) : (
                        <span className="text-red">● Offline</span>
                      )}
                    </td>
                    <td className="px-3.5 py-2.5 border-t border-border text-t2 font-mono">
                      {camera.detect?.fps ?? '—'}
                    </td>
                    <td className="px-3.5 py-2.5 border-t border-border text-t2 font-mono">
                      {status?.total_events ?? 0}
                    </td>
                    <td className="px-3.5 py-2.5 border-t border-border text-t2">
                      {getEnabledRules(camera)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── go2rtc Configuration ── */}
      <div className="mt-5 bg-bg2 rounded-lg border border-border p-4">
        <div className="flex items-center justify-between mb-3.5">
          <div className="flex items-center gap-2">
            <Video size={14} className="text-t3" />
            <h3 className="text-xs font-semibold text-t3 uppercase tracking-wide">go2rtc Configuration</h3>
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-t3 uppercase tracking-wide">WebRTC Candidates (Server IP:Port)</label>
          <input
            type="text"
            placeholder="192.168.104.48:1988"
            value={go2rtcConfig.webrtc_candidates}
            onChange={(e) => setGo2rtcConfig({ ...go2rtcConfig, webrtc_candidates: e.target.value })}
            className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150"
          />
          <span className="text-[9px] text-t3">Enter your server's IP and go2rtc port (e.g. 192.168.104.48:1988). Required for live video streaming.</span>
        </div>
        <div className="flex justify-end mt-3">
          <button
            onClick={handleGo2rtcSave}
            disabled={go2rtcSaving}
            className="px-4 py-1.5 rounded-md bg-green text-bg text-[11px] font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {go2rtcSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* ── Model Configuration ── */}
      <div className="mt-5 bg-bg2 rounded-lg border border-border p-4">
        <div className="flex items-center justify-between mb-3.5">
          <div className="flex items-center gap-2">
            <Cpu size={14} className="text-t3" />
            <h3 className="text-xs font-semibold text-t3 uppercase tracking-wide">Model Configuration</h3>
          </div>
          <span className="text-[9px] text-t3 bg-card px-2 py-0.5 rounded">Requires restart</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Detector Model Path</label>
            <input
              type="text"
              placeholder="data/models/yolo26m.pt"
              value={modelConfig.detector_path}
              onChange={(e) => setModelConfig({ ...modelConfig, detector_path: e.target.value })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150"
            />
            <span className="text-[9px] text-t3">Supports .pt (PyTorch) or .engine (TensorRT)</span>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Pose Model Path</label>
            <input
              type="text"
              placeholder="data/models/yolo26m-pose.pt"
              value={modelConfig.pose_path}
              onChange={(e) => setModelConfig({ ...modelConfig, pose_path: e.target.value })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150"
            />
            <span className="text-[9px] text-t3">Leave empty to disable pose enhancement</span>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Detection Confidence</label>
            <input
              type="number"
              min={0.1}
              max={1.0}
              step={0.05}
              value={modelConfig.confidence}
              onChange={(e) => setModelConfig({ ...modelConfig, confidence: Number(e.target.value) })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150 w-24"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Pose Confidence</label>
            <input
              type="number"
              min={0.1}
              max={1.0}
              step={0.05}
              value={modelConfig.pose_confidence}
              onChange={(e) => setModelConfig({ ...modelConfig, pose_confidence: Number(e.target.value) })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150 w-24"
            />
          </div>
        </div>
        <div className="flex justify-end mt-3">
          <button
            onClick={handleModelSave}
            disabled={modelSaving}
            className="px-4 py-1.5 rounded-md bg-green text-bg text-[11px] font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {modelSaving ? 'Saving...' : 'Save Model Config'}
          </button>
        </div>
      </div>

      {/* ── MQTT Configuration ── */}
      <div className="mt-5 bg-bg2 rounded-lg border border-border p-4">
        <div className="flex items-center justify-between mb-3.5">
          <div className="flex items-center gap-2">
            <Radio size={14} className="text-t3" />
            <h3 className="text-xs font-semibold text-t3 uppercase tracking-wide">MQTT Configuration</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${mqttStatus.connected ? 'bg-green' : 'bg-red'}`} />
            <span className="text-[11px] text-t3 font-mono">
              {mqttStatus.connected ? 'Connected' : 'Disconnected'}
              {mqttStatus.active_sessions > 0 && ` · ${mqttStatus.active_sessions} sessions`}
            </span>
          </div>
        </div>

        {mqttError && (
          <div className="mb-3 px-2 py-1.5 rounded-md bg-red/10 border border-red/20 text-red text-[11px]">
            {mqttError}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Broker Host</label>
            <input
              type="text"
              placeholder="192.168.1.100"
              value={mqttConfig.host}
              onChange={(e) => setMqttConfig({ ...mqttConfig, host: e.target.value })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Port</label>
            <input
              type="number"
              value={mqttConfig.port}
              onChange={(e) => setMqttConfig({ ...mqttConfig, port: parseInt(e.target.value) || 1883 })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Topic</label>
            <input
              type="text"
              placeholder="behavior-detection/events"
              value={mqttConfig.topic}
              onChange={(e) => setMqttConfig({ ...mqttConfig, topic: e.target.value })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Username</label>
            <input
              type="text"
              placeholder="(optional)"
              value={mqttConfig.username}
              onChange={(e) => setMqttConfig({ ...mqttConfig, username: e.target.value })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Password</label>
            <input
              type="password"
              placeholder="(optional)"
              value={mqttConfig.password}
              onChange={(e) => setMqttConfig({ ...mqttConfig, password: e.target.value })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-t3 uppercase tracking-wide">Update Interval (s)</label>
            <input
              type="number"
              value={mqttConfig.update_interval}
              onChange={(e) => setMqttConfig({ ...mqttConfig, update_interval: parseInt(e.target.value) || 30 })}
              className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none focus:border-green transition-colors duration-150"
            />
          </div>
        </div>

        {/* TLS Options */}
        <div className="flex items-center gap-5 mt-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={mqttConfig.tls_enabled}
              onChange={(e) => setMqttConfig({ ...mqttConfig, tls_enabled: e.target.checked, port: e.target.checked && mqttConfig.port === 1883 ? 8883 : (!e.target.checked && mqttConfig.port === 8883 ? 1883 : mqttConfig.port) })}
              className="accent-green"
            />
            <span className="text-[11px] text-t2">Enable TLS/SSL (port 8883)</span>
          </label>
          {mqttConfig.tls_enabled && (
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={mqttConfig.tls_insecure}
                onChange={(e) => setMqttConfig({ ...mqttConfig, tls_insecure: e.target.checked })}
                className="accent-orange"
              />
              <span className="text-[11px] text-t2">Skip certificate verification (self-signed)</span>
            </label>
          )}
        </div>

        <div className="flex items-center justify-between mt-3.5">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={mqttConfig.enabled}
              onChange={(e) => setMqttConfig({ ...mqttConfig, enabled: e.target.checked })}
              className="accent-green"
            />
            <span className="text-[11px] text-t2">Enable MQTT Publishing</span>
          </label>
          <button
            onClick={handleMqttSave}
            disabled={mqttSaving}
            className="px-4 py-1.5 rounded-md bg-green text-bg text-[11px] font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {mqttSaving ? 'Saving...' : 'Save MQTT Config'}
          </button>
        </div>
      </div>
    </div>
  )
}
