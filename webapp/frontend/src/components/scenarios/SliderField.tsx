/**
 * Labeled slider with a numeric input side-by-side.
 * Used throughout the scenario form for capacity, price, and parameter inputs.
 */
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface SliderFieldProps {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  /** Hint text shown below the label. */
  hint?: string;
}

export function SliderField({
  label,
  value,
  onChange,
  min,
  max,
  step = 0.1,
  unit,
  hint,
}: SliderFieldProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <Label className="text-sm">
          {label}
          {unit && (
            <span className="ml-1 text-xs text-muted-foreground">({unit})</span>
          )}
        </Label>
        {hint && (
          <span className="text-xs text-muted-foreground">{hint}</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <Slider
          value={[value]}
          min={min}
          max={max}
          step={step}
          onValueChange={(v) => onChange(v[0])}
          className="flex-1"
        />
        <Input
          type="number"
          value={value}
          step={step}
          min={min}
          max={max}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            if (!isNaN(v)) onChange(v);
          }}
          className="w-24 h-8 text-right"
        />
      </div>
    </div>
  );
}
