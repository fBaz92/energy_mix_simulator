/**
 * Top-level scenario editor form with tabbed layout.
 *
 * Manages local state for a full ScenarioCreate payload. On submit,
 * assembles the payload and calls the provided onSubmit callback.
 *
 * Initial state is derived from the backend /api/scenarios/defaults,
 * or from an existing scenario when editing.
 */
import { useMemo, useState } from "react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { MixSliderGroup } from "./MixSliderGroup";
import { FuelScenarioEditor } from "./FuelScenarioEditor";
import { InterconnectionEditor } from "./InterconnectionEditor";
import { StorageEditor } from "./StorageEditor";
import type {
  DefaultsResponse,
  FuelScenarioParams,
  GeneratorParams,
  InterconnectionParams,
  PriceAreaParams,
  ScenarioCreate,
  StorageParams,
} from "@/types/api";

interface ScenarioFormProps {
  defaults: DefaultsResponse;
  /** Initial form values (for editing an existing scenario). */
  initial?: ScenarioCreate;
  onSubmit: (body: ScenarioCreate) => void;
  onCancel?: () => void;
  submitLabel?: string;
  isSubmitting?: boolean;
}

function buildInitialFromDefaults(d: DefaultsResponse): ScenarioCreate {
  return {
    name: "New Scenario",
    description: "",
    mix_config: structuredClone(d.italian_mix),
    gas_scenario: { ...d.gas_scenarios.base },
    coal_scenario: { ...d.coal_scenarios.base },
    co2_scenario: { ...d.co2_scenarios.base },
    interconnections: null,
    price_areas: structuredClone(d.price_areas),
    price_area_correlations: structuredClone(d.price_area_correlations),
    price_areas_correlated: true,
    enable_ntc_faults: true,
    storage: null,
    n_runs: 20,
    seed: 42,
    load_noise: 0.04,
  };
}

export function ScenarioForm({
  defaults,
  initial,
  onSubmit,
  onCancel,
  submitLabel = "Save scenario",
  isSubmitting,
}: ScenarioFormProps) {
  const initialState = useMemo(
    () => initial ?? buildInitialFromDefaults(defaults),
    [defaults, initial]
  );

  const [name, setName] = useState(initialState.name);
  const [description, setDescription] = useState(initialState.description);
  const [mixConfig, setMixConfig] = useState<Record<string, GeneratorParams>>(
    initialState.mix_config
  );
  const [gasScenario, setGasScenario] = useState<FuelScenarioParams>(
    initialState.gas_scenario
  );
  const [coalScenario, setCoalScenario] = useState<FuelScenarioParams>(
    initialState.coal_scenario ?? defaults.coal_scenarios.base
  );
  const [co2Scenario, setCo2Scenario] = useState<FuelScenarioParams>(
    initialState.co2_scenario ?? defaults.co2_scenarios.base
  );
  const [icEnabled, setIcEnabled] = useState(
    initialState.interconnections !== null
  );
  const [interconnections, setInterconnections] = useState<
    Record<string, InterconnectionParams>
  >(initialState.interconnections ?? structuredClone(defaults.interconnections));
  const [priceAreas, setPriceAreas] = useState<Record<string, PriceAreaParams>>(
    initialState.price_areas ?? structuredClone(defaults.price_areas)
  );
  const [storageEnabled, setStorageEnabled] = useState(
    initialState.storage !== null
  );
  const [storage, setStorage] = useState<Record<string, StorageParams>>(
    initialState.storage ?? structuredClone(defaults.storage_units)
  );
  const [nRuns, setNRuns] = useState(initialState.n_runs);
  const [seed, setSeed] = useState(initialState.seed);

  const handleSubmit = () => {
    const body: ScenarioCreate = {
      name,
      description,
      mix_config: mixConfig,
      gas_scenario: gasScenario,
      coal_scenario: coalScenario,
      co2_scenario: co2Scenario,
      interconnections: icEnabled ? interconnections : null,
      price_areas: icEnabled ? priceAreas : null,
      price_area_correlations: icEnabled
        ? defaults.price_area_correlations
        : null,
      price_areas_correlated: true,
      enable_ntc_faults: true,
      storage: storageEnabled ? storage : null,
      n_runs: nRuns,
      seed: seed,
      load_noise: 0.04,
    };
    onSubmit(body);
  };

  return (
    <div className="space-y-6">
      {/* Meta fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="scenario-name">Scenario name</Label>
          <Input
            id="scenario-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Italian 2030 reference"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="scenario-description">Description</Label>
          <Input
            id="scenario-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional"
          />
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="mix">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="mix">Generation Mix</TabsTrigger>
          <TabsTrigger value="fuel">Fuel Prices</TabsTrigger>
          <TabsTrigger value="interconnections">Interconnections</TabsTrigger>
          <TabsTrigger value="storage">Storage</TabsTrigger>
          <TabsTrigger value="mc">Monte Carlo</TabsTrigger>
        </TabsList>

        <TabsContent value="mix" className="mt-4 space-y-4">
          {Object.entries(mixConfig).map(([tech, params]) => (
            <MixSliderGroup
              key={tech}
              techName={tech}
              params={params}
              onChange={(next) =>
                setMixConfig({ ...mixConfig, [tech]: next })
              }
            />
          ))}
        </TabsContent>

        <TabsContent value="fuel" className="mt-4 space-y-4">
          <FuelScenarioEditor
            label="Gas price (TTF)"
            muUnit="EUR/MWh_th"
            muMax={150}
            value={gasScenario}
            onChange={setGasScenario}
          />
          <FuelScenarioEditor
            label="Coal price"
            muUnit="EUR/MWh_th"
            muMax={50}
            value={coalScenario}
            onChange={setCoalScenario}
          />
          <FuelScenarioEditor
            label="CO₂ price (EU ETS)"
            muUnit="EUR/ton"
            muMax={200}
            value={co2Scenario}
            onChange={setCo2Scenario}
          />
        </TabsContent>

        <TabsContent value="interconnections" className="mt-4">
          <InterconnectionEditor
            enabled={icEnabled}
            onEnabledChange={setIcEnabled}
            interconnections={interconnections}
            onInterconnectionsChange={setInterconnections}
            priceAreas={priceAreas}
            onPriceAreasChange={setPriceAreas}
          />
        </TabsContent>

        <TabsContent value="storage" className="mt-4">
          <StorageEditor
            enabled={storageEnabled}
            onEnabledChange={setStorageEnabled}
            units={storage}
            onUnitsChange={setStorage}
          />
        </TabsContent>

        <TabsContent value="mc" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="n-runs">Number of MC runs</Label>
              <Input
                id="n-runs"
                type="number"
                min={1}
                max={500}
                value={nRuns}
                onChange={(e) => setNRuns(parseInt(e.target.value) || 1)}
              />
              <p className="text-xs text-muted-foreground">
                Higher = more accurate stats but slower. Typical: 20-100.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="seed">Random seed</Label>
              <Input
                id="seed"
                type="number"
                value={seed}
                onChange={(e) => setSeed(parseInt(e.target.value) || 0)}
              />
              <p className="text-xs text-muted-foreground">
                Identical seed → identical results (reproducible).
              </p>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Actions */}
      <div className="flex items-center justify-end gap-2 pt-4 border-t">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : submitLabel}
        </Button>
      </div>
    </div>
  );
}
