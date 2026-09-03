import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Plus, Pencil, Trash2, CheckSquare, Circle, PhoneCall } from "lucide-react";
import clsx from "clsx";
import { Card, Button, Select, StatusBadge, EmptyState, PageSpinner } from "../components/ui";
import { TaskFormModal } from "../components/tasks/TaskFormModal";
import { tasksApi } from "../api/tasks";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";
import type { Task, TaskStatus, TaskType } from "../types";

function useFormatDue() {
  const { t, language } = useLanguage();
  return (dateStr: string | null) => {
    if (!dateStr) return { label: t("tasks.noDueDate"), overdue: false };
    const date = new Date(dateStr);
    const overdue = date.getTime() < Date.now();
    const locale = language === "fa" ? "fa-IR" : undefined;
    return {
      label: date.toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
      overdue,
    };
  };
}

export default function Tasks() {
  const { t } = useLanguage();
  const formatDue = useFormatDue();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "">("pending");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [newTaskType, setNewTaskType] = useState<TaskType>("general");

  const { data, isLoading } = useQuery({
    queryKey: ["tasks", { status: statusFilter }],
    queryFn: () => tasksApi.list({ status: statusFilter || undefined, page_size: 100 }),
  });

  const toggleMutation = useMutation({
    mutationFn: (task: Task) =>
      tasksApi.update(task.id, { status: task.status === "completed" ? "pending" : "completed" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => tasksApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success(t("tasks.deleted"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium text-ink">{t("tasks.title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("tasks.subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setEditing(null);
              setNewTaskType("call");
              setModalOpen(true);
            }}
          >
            <PhoneCall className="h-4 w-4" /> {t("tasks.newCallReminder")}
          </Button>
          <Button
            onClick={() => {
              setEditing(null);
              setNewTaskType("general");
              setModalOpen(true);
            }}
          >
            <Plus className="h-4 w-4" /> {t("tasks.new")}
          </Button>
        </div>
      </div>

      <Card className="p-4">
        <Select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as TaskStatus | "")}
          className="w-48"
        >
          <option value="">{t("tasks.filterAll")}</option>
          <option value="pending">{t("tasks.filterPending")}</option>
          <option value="completed">{t("tasks.filterCompleted")}</option>
        </Select>
      </Card>

      <Card>
        {isLoading ? (
          <PageSpinner />
        ) : data && data.items.length > 0 ? (
          <div className="divide-y divide-border">
            {data.items.map((task) => {
              const due = formatDue(task.due_date);
              const isDone = task.status === "completed";
              return (
                <div key={task.id} className="flex items-center gap-3 px-4 py-3">
                  <button
                    onClick={() => toggleMutation.mutate(task)}
                    className={clsx("shrink-0", isDone ? "text-primary" : "text-muted hover:text-primary")}
                    aria-label={isDone ? t("tasks.markPending") : t("tasks.markComplete")}
                  >
                    {isDone ? <CheckSquare className="h-5 w-5" /> : <Circle className="h-5 w-5" />}
                  </button>
                  {task.task_type === "call" && (
                    <PhoneCall className="h-4 w-4 shrink-0 text-accent" aria-label={t("tasks.type.call")} />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className={clsx("text-sm font-medium", isDone ? "text-muted line-through" : "text-ink")}>
                      {task.title}
                    </p>
                    <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                      <span className={clsx(due.overdue && !isDone && "font-medium text-danger")}>{due.label}</span>
                      {task.contact_name && <span>· {task.contact_name}</span>}
                      {task.deal_title && <span>· {task.deal_title}</span>}
                      {task.assigned_to && <span>· {task.assigned_to.full_name}</span>}
                    </div>
                  </div>
                  <StatusBadge value={task.priority} />
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => {
                        setEditing(task);
                        setModalOpen(true);
                      }}
                      className="rounded p-1.5 text-muted hover:bg-primary/10 hover:text-primary"
                      aria-label={t("common.edit")}
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => {
                        if (window.confirm(t("tasks.confirmDelete"))) deleteMutation.mutate(task.id);
                      }}
                      className="rounded p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
                      aria-label={t("common.delete")}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={<CheckSquare className="h-8 w-8" />}
            title={t("tasks.emptyTitle")}
            description={t("tasks.emptyDescription")}
            action={
              <Button
                onClick={() => {
                  setNewTaskType("general");
                  setModalOpen(true);
                }}
              >
                <Plus className="h-4 w-4" /> {t("tasks.new")}
              </Button>
            }
          />
        )}
      </Card>

      <TaskFormModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditing(null);
        }}
        task={editing}
        defaultTaskType={newTaskType}
      />
    </div>
  );
}
