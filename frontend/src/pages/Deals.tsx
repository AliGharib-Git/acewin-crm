import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Plus } from "lucide-react";
import { Button, PageSpinner, EmptyState } from "../components/ui";
import { KanbanBoard } from "../components/deals/KanbanBoard";
import { DealFormModal } from "../components/deals/DealFormModal";
import { dealsApi } from "../api/deals";
import { pipelineApi } from "../api/pipeline";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";
import type { Deal } from "../types";

export default function Deals() {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Deal | null>(null);
  const [defaultStageId, setDefaultStageId] = useState<number | null>(null);

  const { data: stages, isLoading: loadingStages } = useQuery({ queryKey: ["pipeline-stages"], queryFn: pipelineApi.list });
  const { data: dealsPage, isLoading: loadingDeals } = useQuery({
    queryKey: ["deals", "board"],
    queryFn: () => dealsApi.list({ page_size: 200 }),
  });

  const moveMutation = useMutation({
    mutationFn: ({ id, stageId }: { id: number; stageId: number }) => dealsApi.update(id, { stage_id: stageId }),
    onMutate: async ({ id, stageId }) => {
      await queryClient.cancelQueries({ queryKey: ["deals", "board"] });
      const previous = queryClient.getQueryData<{ items: Deal[]; total: number; page: number; page_size: number }>([
        "deals",
        "board",
      ]);
      if (previous) {
        queryClient.setQueryData(["deals", "board"], {
          ...previous,
          items: previous.items.map((d) => (d.id === id ? { ...d, stage_id: stageId } : d)),
        });
      }
      return { previous };
    },
    onError: (err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(["deals", "board"], context.previous);
      toast.error(errorMessage(err));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  if (loadingStages || loadingDeals) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium text-ink">{t("deals.title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("deals.subtitle")}</p>
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setDefaultStageId(stages?.[0]?.id ?? null);
            setModalOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> {t("deals.new")}
        </Button>
      </div>

      {!stages?.length ? (
        <EmptyState
          title={t("deals.noStagesTitle")}
          description={t("deals.noStagesDescription")}
        />
      ) : (
        <KanbanBoard
          stages={stages}
          deals={dealsPage?.items ?? []}
          onMoveDeal={(dealId, stageId) => moveMutation.mutate({ id: dealId, stageId })}
          onCardClick={(deal) => {
            setEditing(deal);
            setModalOpen(true);
          }}
          onAddDeal={(stageId) => {
            setEditing(null);
            setDefaultStageId(stageId);
            setModalOpen(true);
          }}
        />
      )}

      <DealFormModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditing(null);
        }}
        deal={editing}
        defaultStageId={defaultStageId}
      />
    </div>
  );
}
