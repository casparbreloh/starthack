import { motion } from "framer-motion"

import healthyHerbs from "@/assets/crops/healthy_herbs.png"
import healthyLettuce from "@/assets/crops/healthy_lettuce.png"
// Crop images - healthy
import healthyPotato from "@/assets/crops/healthy_potato.png"
import healthyRadish from "@/assets/crops/healthy_radish.png"
// Empty bed
import plainBed from "@/assets/crops/plain.png"
import unhealthyHerbs from "@/assets/crops/unhealthy_herbs.png"
import unhealthyLettuce from "@/assets/crops/unhealthy_lettuce.png"
// Crop images - unhealthy
import unhealthyPotato from "@/assets/crops/unhealthy_potato.png"
import unhealthyRadish from "@/assets/crops/unhealthy_radish.png"
import type { CropBatch } from "@/types/game"

interface GreenhouseMapProps {
  crops: CropBatch[]
  activeZone: string
}

const CROP_IMAGES: Record<string, { healthy: string; unhealthy: string }> = {
  potato: { healthy: healthyPotato, unhealthy: unhealthyPotato },
  lettuce: { healthy: healthyLettuce, unhealthy: unhealthyLettuce },
  herbs: { healthy: healthyHerbs, unhealthy: unhealthyHerbs },
  radish: { healthy: healthyRadish, unhealthy: unhealthyRadish },
  soybean: { healthy: healthyHerbs, unhealthy: unhealthyHerbs },
}

const HEALTH_THRESHOLD = 60

function getCropImage(crop: CropBatch): string {
  const key = crop.crop_type.toLowerCase()
  const images = CROP_IMAGES[key]
  if (!images) return plainBed
  if (crop.growth_pct <= 5) return plainBed
  return crop.health_pct >= HEALTH_THRESHOLD ? images.healthy : images.unhealthy
}

const BEDS_PER_ZONE = 4

function getZoneBeds(crops: CropBatch[], zoneId: string): (CropBatch | null)[] {
  const zoneCrops = crops.filter((c) => c.zone_id === zoneId)
  const beds: (CropBatch | null)[] = []
  for (let i = 0; i < BEDS_PER_ZONE; i++) {
    beds.push(zoneCrops[i] || null)
  }
  return beds
}

function BedImage({ crop, index }: { crop: CropBatch | null; index: number }) {
  const img = crop ? getCropImage(crop) : plainBed
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.06, type: "spring", stiffness: 400, damping: 30 }}
      className="relative flex items-center justify-center"
    >
      <img
        src={img}
        alt={crop ? `${crop.crop_type} bed` : "Empty bed"}
        className="h-auto w-[280px]"
        draggable={false}
      />
      {crop && (
        <div className="absolute left-1/2 top-1/2 z-10 min-w-[90px] -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded border border-border bg-background/85 px-1.5 py-1 text-center backdrop-blur-sm">
          <div className="mb-0.5 font-mono text-[8px] leading-none text-foreground">
            {crop.crop_type.toUpperCase()}
          </div>
          <div className="mb-px flex items-center gap-1">
            <span className="w-[10px] text-right font-mono text-[7px] text-muted-foreground">
              G
            </span>
            <div className="h-1 flex-1 overflow-hidden rounded-sm bg-secondary">
              <div
                className="h-full rounded-sm bg-primary transition-all duration-500"
                style={{ width: `${crop.growth_pct}%` }}
              />
            </div>
            <span className="w-[22px] text-right font-mono text-[7px] tabular-nums text-foreground">
              {crop.growth_pct}%
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-[10px] text-right font-mono text-[7px] text-muted-foreground">
              HP
            </span>
            <div className="h-1 flex-1 overflow-hidden rounded-sm bg-secondary">
              <div
                className={`h-full rounded-sm transition-all duration-500 ${crop.health_pct >= 60 ? "bg-primary" : crop.health_pct >= 30 ? "bg-amber-alert" : "bg-destructive"}`}
                style={{ width: `${crop.health_pct}%` }}
              />
            </div>
            <span className="w-[22px] text-right font-mono text-[7px] tabular-nums text-foreground">
              {crop.health_pct}%
            </span>
          </div>
          <div className="mt-0.5 font-mono text-[7px] leading-none text-muted-foreground">
            {crop.days_to_harvest}d
          </div>
        </div>
      )}
    </motion.div>
  )
}
export function GreenhouseMap({ crops, activeZone }: GreenhouseMapProps) {
  const beds = getZoneBeds(crops, activeZone)
  const label = activeZone.replace("zone_", "ZONE ").toUpperCase()

  return (
    <motion.div
      key={activeZone}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col items-center justify-center"
    >
      <div className="mb-2 text-center">
        <span className="label-aerospace text-xs tracking-widest text-muted-foreground">
          {label}
        </span>
      </div>
      <div className="flex flex-col items-center">
        <div>
          <BedImage crop={beds[0]} index={0} />
        </div>
        <div className="-mt-48 flex">
          <BedImage crop={beds[1]} index={1} />
          <BedImage crop={beds[2]} index={2} />
        </div>
        <div className="-mt-48">
          <BedImage crop={beds[3]} index={3} />
        </div>
      </div>
    </motion.div>
  )
}
