/**
 * Editor for a single fuel (or CO2) O-U price scenario.
 * Three sliders: mu (mean), sigma (volatility), theta (mean-reversion).
 */
import { Card, CardContent } from "@/components/ui/card";
import { SliderField } from "./SliderField";
import type { FuelScenarioParams } from "@/types/api";

interface FuelScenarioEditorProps {
  label: string;
  /** Unit shown for the mu slider — e.g. "EUR/MWh_th" or "EUR/ton". */
  muUnit: string;
  muMax: number;
  value: FuelScenarioParams;
  onChange: (v: FuelScenarioParams) => void;
}

export function FuelScenarioEditor({
  label,
  muUnit,
  muMax,
  value,
  onChange,
}: FuelScenarioEditorProps) {
  return (
    <Card>
      <CardContent className="pt-4 space-y-4">
        <h3 className="text-base font-semibold">{label}</h3>
        <SliderField
          label="Mean (μ)"
          value={value.mu}
          onChange={(v) => onChange({ ...value, mu: v })}
          min={0}
          max={muMax}
          step={0.5}
          unit={muUnit}
        />
        <SliderField
          label="Volatility (σ)"
          value={value.sigma}
          onChange={(v) => onChange({ ...value, sigma: v })}
          min={0}
          max={muMax / 2}
          step={0.1}
        />
        <SliderField
          label="Mean-reversion (θ)"
          value={value.theta}
          onChange={(v) => onChange({ ...value, theta: v })}
          min={0.01}
          max={0.5}
          step={0.01}
          hint="higher = faster reversion"
        />
      </CardContent>
    </Card>
  );
}
