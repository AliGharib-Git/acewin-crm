import { DragDropContext, Draggable, Droppable, type DropResult } from "@hello-pangea/dnd";
import { Plus } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import type { Deal, PipelineStage } from "../../types";

function useFormatCurrency() {
  const { language } = useLanguage();
  return (value: number) =>
    new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(value);
}

function DealCard({ deal, index }: { deal: Deal; index: number }) {
  const formatCurrency = useFormatCurrency();
  return (
    <Draggable draggableId={String(deal.id)} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className="mb-2 rounded border border-border bg-surface p-3 shadow-card transition-shadow"
          style={{
            ...provided.draggableProps.style,
            boxShadow: snapshot.isDragging ? "0 8px 24px rgba(18,24,28,0.14)" : undefined,
          }}
        >
          <p className="text-sm font-medium text-ink">{deal.title}</p>
          <p className="mt-1 font-mono text-sm tabular text-ink">{formatCurrency(deal.value)}</p>
          <div className="mt-2 flex items-center justify-between text-xs text-muted">
            <span className="truncate">{deal.company_name ?? deal.contact_name ?? "—"}</span>
            <span className="tabular">{deal.probability}%</span>
          </div>
          {deal.assigned_to && (
            <div className="mt-2 flex items-center gap-1.5">
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary-light font-mono text-[10px] font-semibold text-primary-dark">
                {deal.assigned_to.full_name
                  .split(" ")
                  .map((p) => p[0])
                  .slice(0, 2)
                  .join("")}
              </div>
            </div>
          )}
        </div>
      )}
    </Draggable>
  );
}

export function KanbanBoard({
  stages,
  deals,
  onMoveDeal,
  onCardClick,
  onAddDeal,
}: {
  stages: PipelineStage[];
  deals: Deal[];
  onMoveDeal: (dealId: number, stageId: number) => void;
  onCardClick: (deal: Deal) => void;
  onAddDeal: (stageId: number) => void;
}) {
  const { t } = useLanguage();
  const formatCurrency = useFormatCurrency();
  function handleDragEnd(result: DropResult) {
    const { destination, draggableId } = result;
    if (!destination) return;
    const newStageId = Number(destination.droppableId);
    onMoveDeal(Number(draggableId), newStageId);
  }

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {stages.map((stage) => {
          const stageDeals = deals.filter((d) => d.stage_id === stage.id);
          const total = stageDeals.reduce((sum, d) => sum + d.value, 0);
          return (
            <div key={stage.id} className="w-72 shrink-0">
              <div
                className="mb-3 rounded-t border-t-2 bg-surface px-3 py-2.5"
                style={{ borderTopColor: stage.color }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-ink">{stage.name}</span>
                  <span className="font-mono text-xs tabular text-muted">{stageDeals.length}</span>
                </div>
                <p className="mt-0.5 font-mono text-xs tabular text-muted">{formatCurrency(total)}</p>
              </div>

              <Droppable droppableId={String(stage.id)}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className="min-h-[120px] rounded p-1 transition-colors"
                    style={{ backgroundColor: snapshot.isDraggingOver ? "#0F2620" : "transparent" }}
                  >
                    {stageDeals.map((deal, index) => (
                      <div key={deal.id} onClick={() => onCardClick(deal)}>
                        <DealCard deal={deal} index={index} />
                      </div>
                    ))}
                    {provided.placeholder}
                    <button
                      onClick={() => onAddDeal(stage.id)}
                      className="flex w-full items-center justify-center gap-1.5 rounded border border-dashed border-border py-2 text-xs font-medium text-muted hover:border-primary hover:text-primary"
                    >
                      <Plus className="h-3.5 w-3.5" /> {t("deals.new")}
                    </button>
                  </div>
                )}
              </Droppable>
            </div>
          );
        })}
      </div>
    </DragDropContext>
  );
}
