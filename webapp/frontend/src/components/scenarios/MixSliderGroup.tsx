/**
 * Per-technology generator parameter editor.
 * Shows a capacity slider up front, with advanced parameters hidden in an accordion.
 */
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Card, CardContent } from "@/components/ui/card";
import { SliderField } from "./SliderField";
import type { GeneratorParams } from "@/types/api";

interface MixSliderGroupProps {
  techName: string;
  params: GeneratorParams;
  onChange: (next: GeneratorParams) => void;
}

const TECH_LABELS: Record<string, string> = {
  gas: "Gas",
  solar: "Solar PV",
  wind: "Wind",
  nuclear: "Nuclear",
  coal: "Coal",
  hydro_mustrun: "Hydro (must-run)",
};

export function MixSliderGroup({
  techName,
  params,
  onChange,
}: MixSliderGroupProps) {
  const update = <K extends keyof GeneratorParams>(
    key: K,
    v: GeneratorParams[K]
  ) => onChange({ ...params, [key]: v });

  const label = TECH_LABELS[techName] ?? techName;

  return (
    <Card>
      <CardContent className="pt-4 space-y-4">
        <div className="flex items-baseline justify-between">
          <h3 className="text-base font-semibold capitalize">{label}</h3>
          <span className="text-xs text-muted-foreground">{techName}</span>
        </div>

        <SliderField
          label="Installed capacity"
          value={params.capacity_gw}
          onChange={(v) => update("capacity_gw", v)}
          min={0}
          max={80}
          step={0.5}
          unit="GW"
        />

        <Accordion type="single" collapsible>
          <AccordionItem value="advanced" className="border-b-0">
            <AccordionTrigger className="py-2 text-xs text-muted-foreground hover:text-foreground">
              Advanced parameters
            </AccordionTrigger>
            <AccordionContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <SliderField
                  label="Efficiency"
                  value={params.efficiency}
                  onChange={(v) => update("efficiency", v)}
                  min={0.1}
                  max={1.0}
                  step={0.01}
                />
                <SliderField
                  label="Emission factor"
                  value={params.emission_factor}
                  onChange={(v) => update("emission_factor", v)}
                  min={0}
                  max={1.0}
                  step={0.01}
                  unit="tCO₂/MWh_th"
                />
                <SliderField
                  label="Inertia H"
                  value={params.h_inertia}
                  onChange={(v) => update("h_inertia", v)}
                  min={0}
                  max={10}
                  step={0.1}
                  unit="s"
                />
                <SliderField
                  label="Min stable gen"
                  value={params.min_stable_pct}
                  onChange={(v) => update("min_stable_pct", v)}
                  min={0}
                  max={1.0}
                  step={0.05}
                  unit="fraction"
                />
                <SliderField
                  label="VOM cost"
                  value={params.vom_eur_mwh}
                  onChange={(v) => update("vom_eur_mwh", v)}
                  min={0}
                  max={20}
                  step={0.1}
                  unit="EUR/MWh"
                />
                <SliderField
                  label="Ramp rate"
                  value={params.ramp_rate_pct_per_min}
                  onChange={(v) => update("ramp_rate_pct_per_min", v)}
                  min={0}
                  max={1.0}
                  step={0.01}
                  unit="frac/min"
                />
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </CardContent>
    </Card>
  );
}
