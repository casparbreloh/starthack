import { motion } from "framer-motion";
import type { CropBatch } from "@/types/game";

// Crop images - healthy
import healthyPotato from "@/assets/crops/healthy_potato.png";
import healthyLettuce from "@/assets/crops/healthy_lettuce.png";
import healthyHerbs from "@/assets/crops/healthy_herbs.png";
import healthyRadish from "@/assets/crops/healthy_radish.png";
// Crop images - unhealthy
import unhealthyPotato from "@/assets/crops/unhealthy_potato.png";
import unhealthyLettuce from "@/assets/crops/unhealthy_lettuce.png";
import unhealthyHerbs from "@/assets/crops/unhealthy_herbs.png";
import unhealthyRadish from "@/assets/crops/unhealthy_radish.png";
// Empty bed
import plainBed from "@/assets/crops/plain.png";

interface GreenhouseMapProps {
  crops: CropBatch[];
  activeZone: string;
}

const CROP_IMAGES: Record<string, { healthy: string; unhealthy: string }> = {
  potato: { healthy: healthyPotato, unhealthy: unhealthyPotato },
  lettuce: { healthy: healthyLettuce, unhealthy: unhealthyLettuce },
  herbs: { healthy: healthyHerbs, unhealthy: unhealthyHerbs },
  radish: { healthy: healthyRadish, unhealthy: unhealthyRadish },
  soybean: { healthy: healthyHerbs, unhealthy: unhealthyHerbs },
};

const HEALTH_THRESHOLD = 60;

function getCropImage(crop: CropBatch): string {
  const key = crop.crop_type.toLowerCase();
  const images = CROP_IMAGES[key];
  if (!images) return plainBed;
  if (crop.growth_pct <= 5) return plainBed;
  return crop.health_pct >= HEALTH_THRESHOLD ? images.healthy : images.unhealthy;
}

const BEDS_PER_ZONE = 4;

function getZoneBeds(crops: CropBatch[], zoneId: string): (CropBatch | null)[] {
  const zoneCrops = crops.filter((c) => c.zone_id === zoneId);
  const beds: (CropBatch | null)[] = [];
  for (let i = 0; i < BEDS_PER_ZONE; i++) {
    beds.push(zoneCrops[i] || null);
  }
  return beds;
}

function BedImage({ crop, index }: { crop: CropBatch | null; index: number }) {
  const img = crop ? getCropImage(crop) : plainBed;
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
        className="w-[280px] h-auto"
        draggable={false}
      />
      {crop && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-background/85 border border-border rounded px-1.5 py-1 backdrop-blur-sm whitespace-nowrap z-10 text-center min-w-[90px]">
          <div className="font-mono text-[8px] text-foreground mb-0.5 leading-none">
            {crop.crop_type.toUpperCase()}
          </div>
          <div className="flex items-center gap-1 mb-px">
            <span className="font-mono text-[7px] text-muted-foreground w-[10px] text-right">G</span>
            <div className="h-1 flex-1 bg-secondary rounded-sm overflow-hidden">
              <div className="h-full rounded-sm bg-primary transition-all duration-500" style={{ width: `${crop.growth_pct}%` }} />
            </div>
            <span className="font-mono text-[7px] tabular-nums text-foreground w-[22px] text-right">{crop.growth_pct}%</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="font-mono text-[7px] text-muted-foreground w-[10px] text-right">HP</span>
            <div className="h-1 flex-1 bg-secondary rounded-sm overflow-hidden">
              <div className={`h-full rounded-sm transition-all duration-500 ${crop.health_pct >= 60 ? 'bg-primary' : crop.health_pct >= 30 ? 'bg-amber-alert' : 'bg-destructive'}`} style={{ width: `${crop.health_pct}%` }} />
            </div>
            <span className="font-mono text-[7px] tabular-nums text-foreground w-[22px] text-right">{crop.health_pct}%</span>
          </div>
          <div className="font-mono text-[7px] text-muted-foreground mt-0.5 leading-none">
            {crop.days_to_harvest}d
          </div>
        </div>
      )}
    </motion.div>
  );
}
export function GreenhouseMap({ crops, activeZone }: GreenhouseMapProps) {
  const beds = getZoneBeds(crops, activeZone);
  const label = activeZone.replace("zone_", "ZONE ").toUpperCase();

  return (
    <motion.div
      key={activeZone}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col items-center justify-center"
    >
      <div className="text-center mb-2">
        <span className="label-aerospace text-xs text-muted-foreground tracking-widest">{label}</span>
      </div>
      <div className="flex flex-col items-center">
        <div>
          <BedImage crop={beds[0]} index={0} />
        </div>
        <div className="flex -mt-48">
          <BedImage crop={beds[1]} index={1} />
          <BedImage crop={beds[2]} index={2} />
        </div>
        <div className="-mt-48">
          <BedImage crop={beds[3]} index={3} />
        </div>
      </div>
    </motion.div>
  );
}
