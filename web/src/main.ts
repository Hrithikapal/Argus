import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import './style.css'

const HUB = 'http://localhost:8000'
;(window as any).CESIUM_BASE_URL = '/cesium/'

document.body.insertAdjacentHTML('beforeend', '<div id="status">connecting…</div>')
const status = document.getElementById('status')!

const viewer = new Cesium.Viewer('app', {
  baseLayer: new Cesium.ImageryLayer(
    new Cesium.OpenStreetMapImageryProvider({ url: 'https://tile.openstreetmap.org/' })
  ),
  baseLayerPicker: false, geocoder: false, timeline: false, animation: false,
  sceneModePicker: false, navigationHelpButton: false, homeButton: false,
})

// One dot per entity, kept in a primitive collection (fast even with thousands)
const points = new Cesium.PointPrimitiveCollection()
viewer.scene.primitives.add(points)
const byId = new Map<string, Cesium.PointPrimitive>()

async function refresh() {
  try {
    const res = await fetch(`${HUB}/entities?types=flight`)
    const { items } = await res.json()
    const seen = new Set<string>()
    for (const e of items) {
      seen.add(e.id)
      const pos = Cesium.Cartesian3.fromDegrees(e.lon, e.lat, e.alt_m)
      const existing = byId.get(e.id)
      if (existing) {
        existing.position = pos
      } else {
        byId.set(e.id, points.add({ id: e.id, position: pos, pixelSize: 6, color: Cesium.Color.YELLOW }))
      }
    }
    for (const [id, p] of byId) {
      if (!seen.has(id)) { points.remove(p); byId.delete(id) }
    }
    status.textContent = `${items.length} flights`
  } catch (err) {
    status.textContent = 'hub unreachable'
  }
}

refresh()
setInterval(refresh, 5000)

viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(78.487, 17.385, 900_000) })