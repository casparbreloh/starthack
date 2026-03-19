import { motion, AnimatePresence } from "framer-motion"
import { useState, useMemo } from "react"

import healthyHerbs from "../../../assets/crops/healthy_herbs.png"
import healthyLettuce from "../../../assets/crops/healthy_lettuce.png"
// Crop images - healthy
import healthyPotato from "../../../assets/crops/healthy_potato.png"
import healthyRadish from "../../../assets/crops/healthy_radish.png"
// Empty bed
import plainBed from "../../../assets/crops/plain.png"
import unhealthyHerbs from "../../../assets/crops/unhealthy_herbs.png"
import unhealthyLettuce from "../../../assets/crops/unhealthy_lettuce.png"
// Crop images - unhealthy
import unhealthyPotato from "../../../assets/crops/unhealthy_potato.png"
import unhealthyRadish from "../../../assets/crops/unhealthy_radish.png"
import type { Crop, CropsStatus } from "../../../types/simulation.ts"

/* ── Image mapping ──────────────────────────────────────────────────────── */

const CROP_IMAGES: Record<string, { healthy: string; unhealthy: string }> = {
  potato: { healthy: healthyPotato, unhealthy: unhealthyPotato },
  lettuce: { healthy: healthyLettuce, unhealthy: unhealthyLettuce },
  herbs: { healthy: healthyHerbs, unhealthy: unhealthyHerbs },
  radish: { healthy: healthyRadish, unhealthy: unhealthyRadish },
  beans: { healthy: healthyHerbs, unhealthy: unhealthyHerbs }, // beans reuse herbs visuals
}

const HEALTH_THRESHOLD = 0.6
const BEDS_PER_ZONE = 4

/* Isometric grid layout — tune these to adjust pot alignment */
const TILE_W = 260
const TILE_H = Math.round(TILE_W * (512 / 509)) // match image aspect ratio
const ISO_STEP_X = 105 // horizontal offset per grid step
const ISO_STEP_Y = 76 // vertical offset per grid step
const GRID_W = ISO_STEP_X * 2 + TILE_W
const GRID_H = ISO_STEP_Y * 2 + TILE_H

/** Format zone ID for display — "A" → "ZONE A", "zone_a" → "ZONE A" */
function formatZoneLabel(zoneId: string): string {
  const cleaned = zoneId.replace(/^zone[_-]?/i, "").toUpperCase()
  return `ZONE ${cleaned}`
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getCropImage(crop: Crop): string {
  const key = crop.type.toLowerCase()
  const images = CROP_IMAGES[key]
  if (!images) return plainBed
  if (crop.growth_pct <= 5) return plainBed
  return crop.health >= HEALTH_THRESHOLD ? images.healthy : images.unhealthy
}

function getZoneBeds(crops: Crop[], zoneId: string): (Crop | null)[] {
  const zoneCrops = crops.filter((c) => c.zone_id === zoneId)
  const beds: (Crop | null)[] = []
  for (let i = 0; i < BEDS_PER_ZONE; i++) {
    beds.push(zoneCrops[i] ?? null)
  }
  return beds
}

function healthColor(health: number): string {
  if (health >= 0.6) return "var(--color-void-ok)"
  if (health >= 0.3) return "var(--color-void-warn)"
  return "var(--color-void-critical)"
}

function daysToHarvest(crop: Crop): number {
  return Math.max(0, crop.expected_harvest_sol - crop.current_sol)
}

/* ── BedImage ───────────────────────────────────────────────────────────── */

function BedImage({ crop, index }: { crop: Crop | null; index: number }) {
  const img = crop ? getCropImage(crop) : plainBed
  const healthPct = crop ? Math.round(crop.health * 100) : 0

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.06, type: "spring", stiffness: 400, damping: 30 }}
      className="relative flex items-center justify-center"
    >
      <img
        src={img}
        alt={crop ? `${crop.type} bed` : "Empty bed"}
        className="h-auto w-[260px]"
        draggable={false}
      />
      {crop && (
        <div
          className="absolute top-1/2 left-1/2 z-10 min-w-[100px] -translate-x-1/2 -translate-y-1/2 rounded-lg px-2.5 py-1.5 text-center backdrop-blur-md"
          style={{
            background: "rgba(8, 9, 10, 0.82)",
            border: "1px solid var(--color-void-border)",
          }}
        >
          {/* Crop name */}
          <div
            className="mb-1 font-mono text-[9px] leading-none font-semibold tracking-[0.12em] uppercase"
            style={{ color: "var(--color-void-text-secondary)" }}
          >
            {crop.type}
          </div>

          {/* Growth bar */}
          <div className="mb-0.5 flex items-center gap-1.5">
            <span
              className="w-[10px] text-right font-mono text-[8px]"
              style={{ color: "var(--color-void-text-muted)" }}
            >
              G
            </span>
            <div
              className="h-[5px] flex-1 overflow-hidden rounded-sm"
              style={{ background: "var(--color-void-border)" }}
            >
              <div
                className="h-full rounded-sm transition-all duration-500"
                style={{
                  width: `${crop.growth_pct}%`,
                  background: "var(--color-void-accent-dim)",
                }}
              />
            </div>
            <span
              className="w-[26px] text-right font-mono text-[8px] tabular-nums"
              style={{ color: "var(--color-void-text-primary)" }}
            >
              {Math.round(crop.growth_pct)}%
            </span>
          </div>

          {/* Health bar */}
          <div className="flex items-center gap-1.5">
            <span
              className="w-[10px] text-right font-mono text-[8px]"
              style={{ color: "var(--color-void-text-muted)" }}
            >
              HP
            </span>
            <div
              className="h-[5px] flex-1 overflow-hidden rounded-sm"
              style={{ background: "var(--color-void-border)" }}
            >
              <div
                className="h-full rounded-sm transition-all duration-500"
                style={{
                  width: `${healthPct}%`,
                  background: healthColor(crop.health),
                }}
              />
            </div>
            <span
              className="w-[26px] text-right font-mono text-[8px] tabular-nums"
              style={{ color: "var(--color-void-text-primary)" }}
            >
              {healthPct}%
            </span>
          </div>

          {/* Days to harvest */}
          <div
            className="mt-1 font-mono text-[8px] leading-none"
            style={{ color: "var(--color-void-text-tertiary)" }}
          >
            {daysToHarvest(crop)}d to harvest
          </div>
        </div>
      )}
    </motion.div>
  )
}

/* ── Zone tabs ──────────────────────────────────────────────────────────── */

function ZoneTabs({
  zones,
  active,
  onSelect,
}: {
  zones: string[]
  active: string
  onSelect: (z: string) => void
}) {
  return (
    <div className="flex items-center gap-3">
      {zones.map((z) => {
        const isActive = z === active
        return (
          <button
            key={z}
            onClick={() => onSelect(z)}
            className="cursor-pointer rounded px-3.5 py-1.5 font-mono text-[11px] font-semibold tracking-[0.14em] uppercase transition-colors"
            style={{
              background: isActive ? "var(--color-void-surface-elevated)" : "transparent",
              color: isActive
                ? "var(--color-void-text-primary)"
                : "var(--color-void-text-tertiary)",
              border: isActive ? "1px solid var(--color-void-ok)" : "1px solid transparent",
            }}
          >
            {formatZoneLabel(z)}
          </button>
        )
      })}
    </div>
  )
}

/* ── Main component ─────────────────────────────────────────────────────── */

interface GreenhouseMapProps {
  crops: CropsStatus | null
}

export default function GreenhouseMap({ crops }: GreenhouseMapProps) {
  const zones = useMemo(() => {
    if (!crops) return []
    const seen = new Set<string>()
    for (const c of crops.crops) {
      seen.add(c.zone_id)
    }
    // Also include zones from available_area_per_zone (may have empty zones)
    for (const z of Object.keys(crops.available_area_per_zone)) {
      seen.add(z)
    }
    return [...seen].sort()
  }, [crops])

  const [activeZone, setActiveZone] = useState<string>("")

  // Sync active zone when zones change
  const effectiveZone = zones.includes(activeZone) ? activeZone : (zones[0] ?? "")

  if (!crops) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <span
          className="font-mono text-sm tracking-[0.1em]"
          style={{ color: "var(--color-void-text-muted)" }}
        >
          AWAITING CROP DATA...
        </span>
      </div>
    )
  }

  if (zones.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <span
          className="font-mono text-sm tracking-[0.1em]"
          style={{ color: "var(--color-void-text-tertiary)" }}
        >
          NO ZONES AVAILABLE
        </span>
      </div>
    )
  }

  const beds = getZoneBeds(crops.crops, effectiveZone)
  const label = formatZoneLabel(effectiveZone)

  return (
    <div className="flex h-full w-full flex-col items-center px-4 pt-10 pb-4">
      {/* Zone tabs — pinned to top center */}
      {zones.length > 1 && (
        <ZoneTabs zones={zones} active={effectiveZone} onSelect={(z) => setActiveZone(z)} />
      )}

      {/* Spacer pushes label + grid toward vertical center */}
      <div className="flex-1" />

      {/* Zone label — just above the grid */}
      <div className="mb-4 text-center">
        <span
          className="font-mono text-xs font-semibold tracking-[0.2em] uppercase"
          style={{ color: "var(--color-void-text-muted)" }}
        >
          {label}
        </span>
      </div>

      {/* Isometric bed grid */}
      <div className="flex items-center justify-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={effectiveZone}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="relative"
            style={{ width: GRID_W, height: GRID_H }}
          >
            {/* Top */}
            <div className="absolute" style={{ left: ISO_STEP_X, top: 0 }}>
              <BedImage crop={beds[0]} index={0} />
            </div>
            {/* Left */}
            <div className="absolute" style={{ left: 0, top: ISO_STEP_Y }}>
              <BedImage crop={beds[1]} index={1} />
            </div>
            {/* Right */}
            <div className="absolute" style={{ left: ISO_STEP_X * 2, top: ISO_STEP_Y }}>
              <BedImage crop={beds[2]} index={2} />
            </div>
            {/* Bottom */}
            <div className="absolute" style={{ left: ISO_STEP_X, top: ISO_STEP_Y * 2 }}>
              <BedImage crop={beds[3]} index={3} />
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Bottom spacer to balance vertical centering */}
      <div className="flex-1" />
    </div>
  )
}
