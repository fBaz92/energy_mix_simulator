/**
 * Sweeps list + launcher.
 *
 * List view mirrors :mod:`SimulationsPage`: status badge, progress
 * counter, metric summary on completed runs. A dialog form creates
 * new sweeps — the user picks a scenario, chooses 1D vs 2D, picks the
 * override paths from a whitelist, and supplies linspace endpoints
 * ``min..max`` + ``count``. We expand the linspace on the client so
 * the user sees exactly which values will be swept.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Trash2 } from "lucide-react";
import {
  useSweeps,
  useLaunchSweep,
  useDeleteSweep,
} from "@/api/sweeps";
import { useScenarios } from "@/api/scenarios";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Whitelist of sweep-capable override paths shown in the form. */
const PARAMETER_OPTIONS: { value: string; label: string }[] = [
  { value: "mix.gas.capacity_gw", label: "Gas capacity (GW)" },
  { value: "mix.coal.capacity_gw", label: "Coal capacity (GW)" },
  { value: "mix.nuclear.capacity_gw", label: "Nuclear capacity (GW)" },
  { value: "mix.solar.capacity_gw", label: "Solar capacity (GW)" },
  { value: "mix.wind.capacity_gw", label: "Wind capacity (GW)" },
  { value: "mix.hydro_mustrun.capacity_gw", label: "Hydro capacity (GW)" },
  { value: "gas.mu", label: "Gas price μ (EUR/MWh_th)" },
  { value: "coal.mu", label: "Coal price μ (EUR/MWh_th)" },
  { value: "co2.mu", label: "CO₂ price μ (EUR/ton)" },
  { value: "load_noise", label: "Load noise σ" },
];

function statusBadge(status: string) {
  const base = "px-2 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "completed":
      return `${base} bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400`;
    case "running":
      return `${base} bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400`;
    case "pending":
      return `${base} bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400`;
    case "failed":
      return `${base} bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400`;
    default:
      return `${base} bg-muted text-muted-foreground`;
  }
}

/** Expand ``[min, max]`` over ``count`` points — equivalent to numpy's
 * ``linspace`` but in the browser so the user can preview the grid. */
function linspace(min: number, max: number, count: number): number[] {
  if (count <= 1) return [min];
  const step = (max - min) / (count - 1);
  return Array.from({ length: count }, (_, i) => min + step * i);
}

function SweepForm({ onSubmitted }: { onSubmitted: () => void }) {
  const { data: scenarios } = useScenarios();
  const launch = useLaunchSweep();

  const [scenarioId, setScenarioId] = useState<number | "">("");
  const [name, setName] = useState("");
  const [sweepType, setSweepType] = useState<"1d" | "2d">("1d");
  const [paramA, setParamA] = useState(PARAMETER_OPTIONS[2].value);
  const [minA, setMinA] = useState(0);
  const [maxA, setMaxA] = useState(20);
  const [countA, setCountA] = useState(5);
  const [paramB, setParamB] = useState(PARAMETER_OPTIONS[6].value);
  const [minB, setMinB] = useState(30);
  const [maxB, setMaxB] = useState(90);
  const [countB, setCountB] = useState(4);
  const [nRuns, setNRuns] = useState(10);

  const valuesA = linspace(minA, maxA, countA);
  const valuesB = linspace(minB, maxB, countB);
  const total = countA * (sweepType === "2d" ? countB : 1);

  const disabled =
    !scenarioId ||
    !name ||
    countA < 2 ||
    (sweepType === "2d" && countB < 2) ||
    nRuns < 2;

  const handleSubmit = async () => {
    if (disabled || typeof scenarioId !== "number") return;
    await launch.mutateAsync({
      scenario_id: scenarioId,
      name,
      sweep_type: sweepType,
      parameter_a: paramA,
      values_a: valuesA,
      parameter_b: sweepType === "2d" ? paramB : null,
      values_b: sweepType === "2d" ? valuesB : null,
      n_runs_per_point: nRuns,
    });
    onSubmitted();
  };

  return (
    <div className="grid gap-4 py-2">
      <div className="grid gap-2">
        <Label htmlFor="sweep-scenario">Scenario</Label>
        <select
          id="sweep-scenario"
          value={scenarioId}
          onChange={(e) =>
            setScenarioId(e.target.value ? Number(e.target.value) : "")
          }
          className="rounded-md border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="">Select a scenario…</option>
          {scenarios?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-2">
        <Label htmlFor="sweep-name">Sweep name</Label>
        <Input
          id="sweep-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nuclear 0–20 GW"
        />
      </div>

      <div className="grid gap-2">
        <Label>Sweep type</Label>
        <div className="flex gap-2">
          {(["1d", "2d"] as const).map((t) => (
            <Button
              key={t}
              type="button"
              variant={sweepType === t ? "default" : "outline"}
              size="sm"
              onClick={() => setSweepType(t)}
            >
              {t.toUpperCase()}
            </Button>
          ))}
        </div>
      </div>

      <fieldset className="border rounded p-3 grid gap-2">
        <legend className="text-xs px-1 text-muted-foreground">
          Parameter A
        </legend>
        <select
          value={paramA}
          onChange={(e) => setParamA(e.target.value)}
          className="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
        >
          {PARAMETER_OPTIONS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <Label className="text-xs">Min</Label>
            <Input
              type="number"
              value={minA}
              onChange={(e) => setMinA(Number(e.target.value))}
            />
          </div>
          <div>
            <Label className="text-xs">Max</Label>
            <Input
              type="number"
              value={maxA}
              onChange={(e) => setMaxA(Number(e.target.value))}
            />
          </div>
          <div>
            <Label className="text-xs">Points</Label>
            <Input
              type="number"
              min={2}
              value={countA}
              onChange={(e) => setCountA(Number(e.target.value))}
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground tabular-nums">
          {valuesA.map((v) => v.toFixed(2)).join(", ")}
        </p>
      </fieldset>

      {sweepType === "2d" && (
        <fieldset className="border rounded p-3 grid gap-2">
          <legend className="text-xs px-1 text-muted-foreground">
            Parameter B
          </legend>
          <select
            value={paramB}
            onChange={(e) => setParamB(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
          >
            {PARAMETER_OPTIONS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <Label className="text-xs">Min</Label>
              <Input
                type="number"
                value={minB}
                onChange={(e) => setMinB(Number(e.target.value))}
              />
            </div>
            <div>
              <Label className="text-xs">Max</Label>
              <Input
                type="number"
                value={maxB}
                onChange={(e) => setMaxB(Number(e.target.value))}
              />
            </div>
            <div>
              <Label className="text-xs">Points</Label>
              <Input
                type="number"
                min={2}
                value={countB}
                onChange={(e) => setCountB(Number(e.target.value))}
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground tabular-nums">
            {valuesB.map((v) => v.toFixed(2)).join(", ")}
          </p>
        </fieldset>
      )}

      <div className="grid gap-2">
        <Label htmlFor="sweep-nruns">MC runs per grid point</Label>
        <Input
          id="sweep-nruns"
          type="number"
          min={2}
          max={100}
          value={nRuns}
          onChange={(e) => setNRuns(Number(e.target.value))}
        />
      </div>

      <p className="text-xs text-muted-foreground">
        Total: {total} grid points × {nRuns} MC runs ={" "}
        <strong>{total * nRuns}</strong> simulations.
      </p>

      <DialogFooter>
        <Button onClick={handleSubmit} disabled={disabled}>
          Launch sweep
        </Button>
      </DialogFooter>
    </div>
  );
}

export function SweepsPage() {
  const { data: sweeps, isLoading } = useSweeps();
  const deleteMutation = useDeleteSweep();
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleDelete = (id: number) => {
    if (confirm("Delete this sweep?")) deleteMutation.mutate(id);
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Sweeps</h1>
          <p className="text-sm text-muted-foreground">
            Parameter sensitivity analyses: 1D curves and 2D heatmaps.
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-1" />
              New sweep
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Launch a parameter sweep</DialogTitle>
              <DialogDescription>
                Varies one or two parameters of an existing scenario and
                aggregates scalar metrics per grid point.
              </DialogDescription>
            </DialogHeader>
            <SweepForm onSubmitted={() => setDialogOpen(false)} />
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : sweeps && sweeps.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-sm text-muted-foreground">
              No sweeps yet. Click "New sweep" to launch one.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {sweeps?.map((s) => (
            <Card key={s.id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base flex items-center gap-3">
                      <span className="text-muted-foreground font-normal">
                        #{s.id}
                      </span>
                      {s.name}
                      <span className={statusBadge(s.status)}>{s.status}</span>
                      <span className="text-xs text-muted-foreground">
                        {s.sweep_type.toUpperCase()}
                      </span>
                    </CardTitle>
                    <CardDescription>
                      {s.scenario_name} · {s.parameter_a}
                      {s.sweep_type === "2d" && s.parameter_b
                        ? ` × ${s.parameter_b}`
                        : ""}{" "}
                      · {s.progress_total} grid points ·{" "}
                      {s.n_runs_per_point} MC runs each
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => handleDelete(s.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <Link to={`/sweeps/${s.id}`}>Open</Link>
                    </Button>
                  </div>
                </div>
              </CardHeader>
              {(s.status === "pending" || s.status === "running") && (
                <CardContent>
                  <div className="text-xs text-muted-foreground mb-1">
                    Progress: {s.progress_current} / {s.progress_total} grid points
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 transition-all"
                      style={{
                        width: `${(s.progress_current / Math.max(s.progress_total, 1)) * 100}%`,
                      }}
                    />
                  </div>
                </CardContent>
              )}
              {s.status === "failed" && s.error_message && (
                <CardContent>
                  <pre className="text-xs text-destructive bg-destructive/10 p-2 rounded overflow-x-auto max-h-32">
                    {s.error_message.split("\n").slice(-5).join("\n")}
                  </pre>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
