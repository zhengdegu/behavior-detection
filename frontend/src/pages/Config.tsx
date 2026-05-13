import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Pencil, Globe } from 'lucide-react'
import type { Camera, RulesConfig, CreateCameraRequest, CameraMQTTPublishConfig } from '../types'
import { getCameras, createCamera, updateCamera, deleteCamera, getTimeSyncStatus, setCameraTimezone } from '../api'
import type { TimeSyncStatus } from '../api'
import RoiEditor from '../components/RoiEditor'
import RuleForm from '../components/RuleForm'

// ── Default rules matching backend Pydantic defaults ──

const DEFAULT_RULES: RulesConfig = {
  crowd: {
    enabled: true,
    max_count: 5,
    radius: 200,
    confirm_frames: 5,
    cooldown: 60,
  },
  fight: {
    enabled: true,
    proximity_radius: 150,
    min_speed: 60,
    min_persons: 2,
    confirm_frames: 3,
    cooldown: 30,
  },
  fall: {
    enabled: true,
    ratio_threshold: 1.0,
    min_ratio_change: 0.5,
    min_y_drop: 20,
    confirm_frames: 2,
    cooldown: 30,
  },
}

const DEFAULT_MQTT_PUBLISH: CameraMQTTPublishConfig = {
  enabled: false,
  crowd: true,
  fight: true,
  fall: true,
}

export default function Config() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Add-form fields
  const [newId, setNewId] = useState('')
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')

  // Editing state for selected camera
  const [editRoi, setEditRoi] = useState<[number, number][]>([])
  const [editRules, setEditRules] = useState<RulesConfig>(DEFAULT_RULES)
  const [editName, setEditName] = useState('')
  const [editUrl, setEditUrl] = useState('')
  const [editMqttPublish, setEditMqttPublish] = useState<CameraMQTTPublishConfig>(DEFAULT_MQTT_PUBLISH)

  // Timezone state
  const [timeSyncStatus, setTimeSyncStatus] = useState<TimeSyncStatus | null>(null)
  const [savingTimezone, setSavingTimezone] = useState(false)

  // ── Fetch cameras on mount ──

  const fetchCameras = useCallback(async () => {
    try {
      const [list, syncStatus] = await Promise.all([getCameras(), getTimeSyncStatus()])
      setCameras(list)
      setTimeSyncStatus(syncStatus)
    } catch {
      // silently ignore fetch errors on mount
    }
  }, [])

  useEffect(() => {
    fetchCameras()
  }, [fetchCameras])

  // ── Sync editing state when selection changes ──

  const selected = cameras.find((c) => c.id === selectedId) ?? null

  useEffect(() => {
    if (selected) {
      setEditRoi(selected.roi ?? [])
      setEditRules(selected.rules ?? DEFAULT_RULES)
      setEditName(selected.name)
      setEditUrl(selected.url)
      setEditMqttPublish(selected.mqtt_publish ?? DEFAULT_MQTT_PUBLISH)
    }
  }, [selected])

  // ── Timezone change ──

  const handleTimezoneChange = async (tz: string) => {
    if (!selectedId) return
    setSavingTimezone(true)
    try {
      await setCameraTimezone(selectedId, tz)
      const syncStatus = await getTimeSyncStatus()
      setTimeSyncStatus(syncStatus)
    } catch {
      // silently ignore
    } finally {
      setSavingTimezone(false)
    }
  }

  // ── Add camera ──

  const handleAdd = async () => {
    if (!newId.trim() || !newName.trim() || !newUrl.trim()) return
    setError(null)
    try {
      const req: CreateCameraRequest = {
        id: newId.trim(),
        name: newName.trim(),
        url: newUrl.trim(),
      }
      await createCamera(req)
      setNewId('')
      setNewName('')
      setNewUrl('')
      setShowAddForm(false)
      await fetchCameras()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Add failed')
    }
  }

  // ── Delete camera ──

  const handleDelete = async (id: string) => {
    setError(null)
    try {
      await deleteCamera(id)
      if (selectedId === id) setSelectedId(null)
      await fetchCameras()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    }
  }

  // ── Save configuration ──

  const handleSave = async () => {
    if (!selectedId) return
    setSaving(true)
    setError(null)
    try {
      await updateCamera(selectedId, { name: editName, url: editUrl, roi: editRoi, rules: editRules, mqtt_publish: editMqttPublish })
      await fetchCameras()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-3.5 grid-cols-1 lg:grid-cols-[280px_1fr]">
      {/* ── Left: Camera list panel ── */}
      <div className="bg-bg2 rounded-lg border border-border p-2.5">
        {/* Header */}
        <div className="flex items-center justify-between mb-2.5">
          <h3 className="text-xs font-semibold text-t3">Cameras</h3>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-green text-bg text-[11px] font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150"
          >
            <Plus size={12} />
            Add
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-2 px-2 py-1.5 rounded-md bg-red/10 border border-red/20 text-red text-[11px]">
            {error}
          </div>
        )}

        {/* Inline add form */}
        {showAddForm && (
          <div className="mb-2.5 p-2.5 rounded-md bg-card border border-border">
            <div className="flex flex-col gap-1.5">
              <input
                type="text"
                placeholder="Camera ID"
                value={newId}
                onChange={(e) => setNewId(e.target.value)}
                className="px-2 py-1.5 rounded-md bg-bg2 text-t1 border border-border font-mono text-[11px] outline-none w-full focus:border-green transition-colors duration-150"
              />
              <input
                type="text"
                placeholder="Name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="px-2 py-1.5 rounded-md bg-bg2 text-t1 border border-border font-mono text-[11px] outline-none w-full focus:border-green transition-colors duration-150"
              />
              <input
                type="text"
                placeholder="RTSP URL"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                className="px-2 py-1.5 rounded-md bg-bg2 text-t1 border border-border font-mono text-[11px] outline-none w-full focus:border-green transition-colors duration-150"
              />
              <div className="flex gap-1.5 mt-1">
                <button
                  onClick={handleAdd}
                  className="flex-1 py-1.5 rounded-md bg-green text-bg text-[11px] font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150"
                >
                  Create
                </button>
                <button
                  onClick={() => {
                    setShowAddForm(false)
                    setNewId('')
                    setNewName('')
                    setNewUrl('')
                  }}
                  className="flex-1 py-1.5 rounded-md bg-card text-t2 text-[11px] border border-border cursor-pointer hover:text-t1 hover:border-hover transition-colors duration-150"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Camera list */}
        <div className="flex flex-col gap-0.5">
          {cameras.map((cam) => (
            <div
              key={cam.id}
              onClick={() => setSelectedId(cam.id)}
              className={`flex items-center justify-between px-2.5 py-2 rounded-md cursor-pointer transition-all duration-150 ${
                selectedId === cam.id
                  ? 'bg-card border-l-2 border-l-green'
                  : 'hover:bg-card'
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="text-xs font-medium text-t1 truncate">
                  {cam.name}
                </div>
                <div className="font-mono text-[9px] text-t3 truncate mt-0.5">
                  {cam.url}
                </div>
              </div>
              <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    cam.online ? 'bg-green' : 'bg-red'
                  }`}
                />
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedId(cam.id)
                  }}
                  className="text-t3 hover:text-green cursor-pointer transition-colors duration-150"
                  aria-label={`Edit camera ${cam.name}`}
                >
                  <Pencil size={12} />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(cam.id)
                  }}
                  className="text-t3 hover:text-red cursor-pointer transition-colors duration-150"
                  aria-label={`Delete camera ${cam.name}`}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          ))}

          {cameras.length === 0 && !showAddForm && (
            <div className="text-center py-6 text-t3 text-[11px]">
              No cameras configured.
              <br />
              Click "+ Add" to get started.
            </div>
          )}
        </div>
      </div>

      {/* ── Right: Editor area ── */}
      {selected ? (
        <div className="bg-bg2 rounded-lg border border-border grid grid-cols-1 lg:grid-cols-2">
          {/* ROI side */}
          <div className="p-3.5 border-b lg:border-b-0 lg:border-r border-border flex flex-col">
            {/* Camera info edit */}
            <div className="mb-3 flex flex-col gap-1.5">
              <label className="text-[10px] text-t3 uppercase tracking-wide">Name</label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none w-full focus:border-green transition-colors duration-150"
              />
              <label className="text-[10px] text-t3 uppercase tracking-wide mt-1">RTSP URL</label>
              <input
                type="text"
                value={editUrl}
                onChange={(e) => setEditUrl(e.target.value)}
                className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border font-mono text-[11px] outline-none w-full focus:border-green transition-colors duration-150"
              />
            </div>
            <h3 className="text-xs font-semibold text-t3 mb-2.5">
              ROI — {editName || selected.name}
            </h3>
            <RoiEditor
              cameraId={selected.id}
              initialVertices={editRoi}
              onVerticesChange={setEditRoi}
            />
          </div>

          {/* Rules side */}
          <div className="p-3.5 overflow-y-auto max-h-[calc(100vh-92px)]">
            <h3 className="text-xs font-semibold text-t3 mb-3.5">
              Detection Rules
            </h3>
            <RuleForm rules={editRules} onChange={setEditRules} />
            {/* MQTT Publish Config */}
            <div className="mt-3.5 pt-3.5 border-t border-border">
              <h4 className="text-[10px] font-semibold text-t3 uppercase tracking-wide mb-2.5">
                MQTT Publishing
              </h4>
              <div className="flex flex-col gap-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editMqttPublish.enabled}
                    onChange={(e) => setEditMqttPublish({ ...editMqttPublish, enabled: e.target.checked })}
                    className="accent-green"
                  />
                  <span className="text-[11px] text-t2">Enable MQTT for this camera</span>
                </label>
                {editMqttPublish.enabled && (
                  <div className="ml-5 flex flex-col gap-1.5">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editMqttPublish.crowd}
                        onChange={(e) => setEditMqttPublish({ ...editMqttPublish, crowd: e.target.checked })}
                        className="accent-green"
                      />
                      <span className="text-[11px] text-t3">Crowd events</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editMqttPublish.fight}
                        onChange={(e) => setEditMqttPublish({ ...editMqttPublish, fight: e.target.checked })}
                        className="accent-green"
                      />
                      <span className="text-[11px] text-t3">Fight events</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editMqttPublish.fall}
                        onChange={(e) => setEditMqttPublish({ ...editMqttPublish, fall: e.target.checked })}
                        className="accent-green"
                      />
                      <span className="text-[11px] text-t3">Fall events</span>
                    </label>
                  </div>
                )}
              </div>
            </div>

            {/* Timezone */}
            <div className="mt-3.5 pt-3.5 border-t border-border">
              <h4 className="text-[10px] font-semibold text-t3 uppercase tracking-wide mb-2.5 flex items-center gap-1.5">
                <Globe size={11} />
                Timezone
              </h4>

              {(() => {
                const syncInfo = timeSyncStatus?.cameras.find((c) => c.camera_id === selectedId)
                const currentTz = syncInfo?.timezone ?? ''
                const offset = syncInfo?.effective_offset ?? 0

                const COMMON_TIMEZONES = [
                  { value: '', label: 'Server time (default)' },
                  { value: 'Asia/Shanghai', label: 'Asia/Shanghai (UTC+8)' },
                  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
                  { value: 'Asia/Seoul', label: 'Asia/Seoul (UTC+9)' },
                  { value: 'Asia/Singapore', label: 'Asia/Singapore (UTC+8)' },
                  { value: 'Asia/Kolkata', label: 'Asia/Kolkata (UTC+5:30)' },
                  { value: 'Asia/Dubai', label: 'Asia/Dubai (UTC+4)' },
                  { value: 'Asia/Bangkok', label: 'Asia/Bangkok (UTC+7)' },
                  { value: 'Asia/Ho_Chi_Minh', label: 'Asia/Ho_Chi_Minh (UTC+7)' },
                  { value: 'Asia/Jakarta', label: 'Asia/Jakarta (UTC+7)' },
                  { value: 'Asia/Taipei', label: 'Asia/Taipei (UTC+8)' },
                  { value: 'Asia/Hong_Kong', label: 'Asia/Hong_Kong (UTC+8)' },
                  { value: 'Europe/London', label: 'Europe/London (UTC+0/+1)' },
                  { value: 'Europe/Paris', label: 'Europe/Paris (UTC+1/+2)' },
                  { value: 'Europe/Berlin', label: 'Europe/Berlin (UTC+1/+2)' },
                  { value: 'Europe/Moscow', label: 'Europe/Moscow (UTC+3)' },
                  { value: 'America/New_York', label: 'America/New_York (UTC-5/-4)' },
                  { value: 'America/Chicago', label: 'America/Chicago (UTC-6/-5)' },
                  { value: 'America/Denver', label: 'America/Denver (UTC-7/-6)' },
                  { value: 'America/Los_Angeles', label: 'America/Los_Angeles (UTC-8/-7)' },
                  { value: 'Australia/Sydney', label: 'Australia/Sydney (UTC+10/+11)' },
                  { value: 'Pacific/Auckland', label: 'Pacific/Auckland (UTC+12/+13)' },
                  { value: 'UTC', label: 'UTC (UTC+0)' },
                ]

                return (
                  <div className="flex flex-col gap-2">
                    <select
                      value={currentTz}
                      onChange={(e) => handleTimezoneChange(e.target.value)}
                      disabled={savingTimezone}
                      className="px-2 py-1.5 rounded-md bg-card text-t1 border border-border text-[11px] outline-none w-full focus:border-green transition-colors duration-150 cursor-pointer disabled:opacity-50"
                    >
                      {COMMON_TIMEZONES.map((tz) => (
                        <option key={tz.value} value={tz.value}>
                          {tz.label}
                        </option>
                      ))}
                    </select>
                    {currentTz && (
                      <div className="flex items-center gap-2 text-[11px]">
                        <span className="text-t3">Offset vs server:</span>
                        <span className="text-green font-mono">
                          {offset >= 0 ? '+' : ''}{offset.toFixed(0)}s
                        </span>
                      </div>
                    )}
                    {!currentTz && (
                      <span className="text-[10px] text-t3">
                        Camera uses server time. Select a timezone if the camera clock differs.
                      </span>
                    )}
                  </div>
                )
              })()}
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full mt-3.5 py-2 rounded-md bg-green text-bg text-xs font-semibold cursor-pointer hover:opacity-85 transition-opacity duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-bg2 rounded-lg border border-border flex items-center justify-center min-h-[400px]">
          <div className="text-center text-t3 text-sm">
            <p>Select a camera from the list to configure</p>
            <p className="text-[11px] mt-1">
              or click "+ Add" to add a new camera
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
