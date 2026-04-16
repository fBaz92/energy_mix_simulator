/**
 * Scenarios list page.
 * - Header with "New scenario" button (opens dialog with ScenarioForm).
 * - Grid of saved scenarios. Click to edit, or "Run" to launch a simulation.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Trash2, Play, Pencil } from "lucide-react";
import {
  useScenarios,
  useCreateScenario,
  useUpdateScenario,
  useDeleteScenario,
  useDefaults,
  useScenario,
} from "@/api/scenarios";
import { useLaunchSimulation } from "@/api/simulations";
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
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScenarioForm } from "@/components/scenarios/ScenarioForm";
import type { ScenarioCreate } from "@/types/api";

export function ScenariosPage() {
  const navigate = useNavigate();
  const [editId, setEditId] = useState<number | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const { data: scenarios, isLoading } = useScenarios();
  const { data: defaults } = useDefaults();
  const { data: editScenario } = useScenario(editId);
  const createMutation = useCreateScenario();
  const updateMutation = useUpdateScenario();
  const deleteMutation = useDeleteScenario();
  const launchMutation = useLaunchSimulation();

  const handleCreate = async (body: ScenarioCreate) => {
    await createMutation.mutateAsync(body);
    setIsCreateOpen(false);
  };

  const handleUpdate = async (body: ScenarioCreate) => {
    if (editId === null) return;
    await updateMutation.mutateAsync({ id: editId, body });
    setEditId(null);
  };

  const handleDelete = (id: number) => {
    if (confirm("Delete this scenario and all its simulations?")) {
      deleteMutation.mutate(id);
    }
  };

  const handleLaunch = async (scenarioId: number) => {
    const sim = await launchMutation.mutateAsync(scenarioId);
    navigate(`/simulations/${sim.id}`);
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Scenarios</h1>
          <p className="text-sm text-muted-foreground">
            Define energy mix configurations to simulate.
          </p>
        </div>
        <Button onClick={() => setIsCreateOpen(true)} disabled={!defaults}>
          <Plus className="h-4 w-4 mr-1" />
          New scenario
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : scenarios && scenarios.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-sm text-muted-foreground mb-4">
              No scenarios yet. Create your first one to start simulating.
            </p>
            <Button onClick={() => setIsCreateOpen(true)} disabled={!defaults}>
              <Plus className="h-4 w-4 mr-1" />
              New scenario
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {scenarios?.map((s) => (
            <Card key={s.id} className="flex flex-col">
              <CardHeader>
                <CardTitle className="text-base">{s.name}</CardTitle>
                <CardDescription>
                  {s.description || (
                    <span className="italic">No description</span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1 flex items-end justify-between gap-2">
                <span className="text-xs text-muted-foreground">
                  Created {new Date(s.created_at).toLocaleDateString()}
                </span>
                <div className="flex gap-1">
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => setEditId(s.id)}
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => handleDelete(s.id)}
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleLaunch(s.id)}
                    disabled={launchMutation.isPending}
                  >
                    <Play className="h-4 w-4 mr-1" />
                    Run
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>New scenario</DialogTitle>
            <DialogDescription>
              Configure the generation mix, fuel prices, and other parameters.
            </DialogDescription>
          </DialogHeader>
          {defaults && (
            <ScenarioForm
              defaults={defaults}
              onSubmit={handleCreate}
              onCancel={() => setIsCreateOpen(false)}
              submitLabel="Create scenario"
              isSubmitting={createMutation.isPending}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog
        open={editId !== null}
        onOpenChange={(o) => !o && setEditId(null)}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Edit scenario</DialogTitle>
          </DialogHeader>
          {defaults && editScenario && (
            <ScenarioForm
              defaults={defaults}
              initial={editScenario.config}
              onSubmit={handleUpdate}
              onCancel={() => setEditId(null)}
              submitLabel="Save changes"
              isSubmitting={updateMutation.isPending}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
