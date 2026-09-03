import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Modal, Button, Input, Select, Textarea } from "../ui";
import { tasksApi, type TaskInput } from "../../api/tasks";
import { contactsApi } from "../../api/contacts";
import { dealsApi } from "../../api/deals";
import { usersApi } from "../../api/users";
import { errorMessage } from "../../api/client";
import { useLanguage } from "../../context/LanguageContext";
import type { Task, TaskPriority, TaskType } from "../../types";

const PRIORITIES: TaskPriority[] = ["low", "medium", "high"];
const TASK_TYPES: TaskType[] = ["general", "call"];
const REMINDER_OPTIONS = [0, 5, 15, 30, 60];

const emptyForm: TaskInput = {
  title: "",
  description: "",
  due_date: "",
  priority: "medium",
  task_type: "general",
  reminder_minutes_before: 15,
  assigned_to_id: null,
  contact_id: null,
  deal_id: null,
};

function toDatetimeLocal(value: string | null | undefined) {
  if (!value) return "";
  return value.slice(0, 16);
}

export function TaskFormModal({
  open,
  onClose,
  task,
  defaultTaskType,
  defaultContactId,
}: {
  open: boolean;
  onClose: () => void;
  task?: Task | null;
  defaultTaskType?: TaskType;
  defaultContactId?: number | null;
}) {
  const { t } = useLanguage();
  const [form, setForm] = useState<TaskInput>(emptyForm);
  const queryClient = useQueryClient();

  const { data: contactsPage } = useQuery({
    queryKey: ["contacts", "all"],
    queryFn: () => contactsApi.list({ page_size: 100 }),
    enabled: open,
  });
  const { data: dealsPage } = useQuery({
    queryKey: ["deals", "all"],
    queryFn: () => dealsApi.list({ page_size: 100 }),
    enabled: open,
  });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: usersApi.list, enabled: open });

  useEffect(() => {
    if (task) {
      setForm({
        title: task.title,
        description: task.description ?? "",
        due_date: toDatetimeLocal(task.due_date),
        priority: task.priority,
        task_type: task.task_type,
        reminder_minutes_before: task.reminder_minutes_before ?? 15,
        assigned_to_id: task.assigned_to?.id ?? null,
        contact_id: task.contact_id,
        deal_id: task.deal_id,
      });
    } else {
      setForm({
        ...emptyForm,
        task_type: defaultTaskType ?? "general",
        contact_id: defaultContactId ?? null,
      });
    }
  }, [task, open, defaultTaskType, defaultContactId]);

  const mutation = useMutation({
    mutationFn: (data: TaskInput) => (task ? tasksApi.update(task.id, data) : tasksApi.create(data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(task ? t("tasks.editTask") : t("tasks.newTask"));
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) {
      toast.error(t("common.titleRequired"));
      return;
    }
    mutation.mutate({
      ...form,
      due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
      description: form.description || null,
    });
  }

  const isCall = form.task_type === "call";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={task ? t("tasks.editTask") : isCall ? t("tasks.newCallReminder") : t("tasks.newTask")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSubmit} isLoading={mutation.isPending}>
            {task ? t("common.save") : t("common.create")}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Select
          label={t("tasks.taskType")}
          value={form.task_type}
          onChange={(e) => setForm({ ...form, task_type: e.target.value as TaskType })}
        >
          {TASK_TYPES.map((tt) => (
            <option key={tt} value={tt}>
              {t(tt === "call" ? "tasks.type.call" : "tasks.type.general")}
            </option>
          ))}
        </Select>
        <Input
          label={t("common.title")}
          required
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
        <Textarea
          label={t("common.description")}
          value={form.description ?? ""}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label={t("common.dueDate")}
            type="datetime-local"
            value={form.due_date ?? ""}
            onChange={(e) => setForm({ ...form, due_date: e.target.value })}
          />
          <Select
            label={t("common.priority")}
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value as TaskPriority })}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {t(`common.${p}` as "common.low" | "common.medium" | "common.high")}
              </option>
            ))}
          </Select>
        </div>
        {isCall && (
          <Select
            label={t("tasks.reminder")}
            value={String(form.reminder_minutes_before ?? 0)}
            onChange={(e) => setForm({ ...form, reminder_minutes_before: Number(e.target.value) })}
          >
            {REMINDER_OPTIONS.map((minutes) => (
              <option key={minutes} value={minutes}>
                {minutes === 0 ? t("tasks.reminder.atDue") : t(`tasks.reminder.${minutes}` as "tasks.reminder.5")}
              </option>
            ))}
          </Select>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Select
            label={t("common.relatedContact")}
            value={form.contact_id ?? ""}
            onChange={(e) => setForm({ ...form, contact_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">{t("common.none")}</option>
            {contactsPage?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.first_name} {c.last_name}
              </option>
            ))}
          </Select>
          <Select
            label={t("common.relatedDeal")}
            value={form.deal_id ?? ""}
            onChange={(e) => setForm({ ...form, deal_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">{t("common.none")}</option>
            {dealsPage?.items.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title}
              </option>
            ))}
          </Select>
        </div>
        <Select
          label={t("common.assignedTo")}
          value={form.assigned_to_id ?? ""}
          onChange={(e) => setForm({ ...form, assigned_to_id: e.target.value ? Number(e.target.value) : null })}
        >
          <option value="">{t("common.unassigned")}</option>
          {users?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name}
            </option>
          ))}
        </Select>
      </form>
    </Modal>
  );
}
