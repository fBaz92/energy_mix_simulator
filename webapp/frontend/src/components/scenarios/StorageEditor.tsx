/**
 * Storage tab content.
 * Top-level toggle + sliders for each BESS unit (energy capacity, power,
 * round-trip efficiency).
 */
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { SliderField } from "./SliderField";
import type { StorageParams } from "@/types/api";

interface StorageEditorProps {
  enabled: boolean;
  onEnabledChange: (v: boolean) => void;
  units: Record<string, StorageParams>;
  onUnitsChange: (v: Record<string, StorageParams>) => void;
}

export function StorageEditor({
  enabled,
  onEnabledChange,
  units,
  onUnitsChange,
}: StorageEditorProps) {
  const updateUnit = (name: string, patch: Partial<StorageParams>) => {
    onUnitsChange({
      ...units,
      [name]: { ...units[name], ...patch },
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 p-4 border rounded-lg bg-card">
        <Switch
          checked={enabled}
          onCheckedChange={onEnabledChange}
          id="stor-enable"
        />
        <Label htmlFor="stor-enable" className="cursor-pointer">
          Enable battery storage
        </Label>
      </div>

      {enabled &&
        Object.entries(units).map(([name, unit]) => (
          <Card key={name}>
            <CardContent className="pt-4 space-y-4">
              <h3 className="text-base font-semibold">{name}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <SliderField
                  label="Energy capacity"
                  value={unit.energy_capacity_gwh}
                  onChange={(v) =>
                    updateUnit(name, { energy_capacity_gwh: v })
                  }
                  min={0.5}
                  max={20}
                  step={0.5}
                  unit="GWh"
                />
                <SliderField
                  label="Power capacity"
                  value={unit.power_capacity_gw}
                  onChange={(v) =>
                    updateUnit(name, { power_capacity_gw: v })
                  }
                  min={0.5}
                  max={10}
                  step={0.5}
                  unit="GW"
                />
                <SliderField
                  label="Round-trip efficiency"
                  value={unit.efficiency_roundtrip}
                  onChange={(v) =>
                    updateUnit(name, { efficiency_roundtrip: v })
                  }
                  min={0.5}
                  max={0.98}
                  step={0.01}
                />
                <SliderField
                  label="Synthetic inertia"
                  value={unit.h_synthetic}
                  onChange={(v) => updateUnit(name, { h_synthetic: v })}
                  min={0}
                  max={10}
                  step={0.1}
                  unit="s"
                />
              </div>
            </CardContent>
          </Card>
        ))}
    </div>
  );
}
