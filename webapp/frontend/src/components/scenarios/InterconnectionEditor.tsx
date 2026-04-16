/**
 * Interconnections tab content.
 * Top-level toggle + per-link NTC sliders for each cross-border link.
 */
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { SliderField } from "./SliderField";
import type {
  InterconnectionParams,
  PriceAreaParams,
} from "@/types/api";

interface InterconnectionEditorProps {
  enabled: boolean;
  onEnabledChange: (v: boolean) => void;
  interconnections: Record<string, InterconnectionParams>;
  onInterconnectionsChange: (
    v: Record<string, InterconnectionParams>
  ) => void;
  priceAreas: Record<string, PriceAreaParams>;
  onPriceAreasChange: (v: Record<string, PriceAreaParams>) => void;
}

export function InterconnectionEditor({
  enabled,
  onEnabledChange,
  interconnections,
  onInterconnectionsChange,
  priceAreas,
  onPriceAreasChange,
}: InterconnectionEditorProps) {
  const updateLink = (
    name: string,
    patch: Partial<InterconnectionParams>
  ) => {
    onInterconnectionsChange({
      ...interconnections,
      [name]: { ...interconnections[name], ...patch },
    });
  };

  const updateArea = (name: string, patch: Partial<PriceAreaParams>) => {
    onPriceAreasChange({
      ...priceAreas,
      [name]: { ...priceAreas[name], ...patch },
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 p-4 border rounded-lg bg-card">
        <Switch
          checked={enabled}
          onCheckedChange={onEnabledChange}
          id="ic-enable"
        />
        <Label htmlFor="ic-enable" className="cursor-pointer">
          Enable cross-border interconnections
        </Label>
      </div>

      {enabled && (
        <div className="space-y-4">
          {Object.entries(interconnections).map(([name, link]) => {
            const area = priceAreas[link.price_area];
            return (
              <Card key={name}>
                <CardContent className="pt-4 space-y-4">
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-base font-semibold">{name}</h3>
                    <span className="text-xs text-muted-foreground">
                      → {link.price_area}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <SliderField
                      label="NTC Import"
                      value={link.ntc_import_gw}
                      onChange={(v) =>
                        updateLink(name, { ntc_import_gw: v })
                      }
                      min={0}
                      max={10}
                      step={0.1}
                      unit="GW"
                    />
                    <SliderField
                      label="NTC Export"
                      value={link.ntc_export_gw}
                      onChange={(v) =>
                        updateLink(name, { ntc_export_gw: v })
                      }
                      min={0}
                      max={10}
                      step={0.1}
                      unit="GW"
                    />
                    <SliderField
                      label="Transport cost"
                      value={link.transport_cost_eur_mwh}
                      onChange={(v) =>
                        updateLink(name, { transport_cost_eur_mwh: v })
                      }
                      min={0}
                      max={15}
                      step={0.5}
                      unit="EUR/MWh"
                    />
                    {area && (
                      <SliderField
                        label={`Foreign price μ (${link.price_area})`}
                        value={area.mu}
                        onChange={(v) =>
                          updateArea(link.price_area, { mu: v })
                        }
                        min={20}
                        max={150}
                        step={1}
                        unit="EUR/MWh"
                      />
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
