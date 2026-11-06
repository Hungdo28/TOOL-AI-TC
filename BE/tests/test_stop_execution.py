import unittest
from types import SimpleNamespace

from services.ai_pipeline_service import AiPipelineService, TaskCancelledError
from services.execution_tracker import ExecutionTracker
from services.task_service import TaskService


class FakeWorkspace:
    def __init__(self):
        self.tasks = [
            {"id": "t1", "Bài toán": "Task Test 1", "Trạng thái": "Waiting", "URL": ""},
            {"id": "t2", "Bài toán": "Task Test 2", "Trạng thái": "Chưa làm", "URL": ""},
        ]

    def list_tasks(self):
        return [dict(t) for t in self.tasks]

    def find_task(self, name):
        return next((t for t in self.tasks if t["Bài toán"].casefold() == name.casefold() or t["id"] == name), None)

    def update_task(self, ident, changes):
        task = self.find_task(ident)
        if not task:
            raise KeyError(ident)
        task.update(changes)
        return task


class StopExecutionTests(unittest.TestCase):
    def test_pipeline_cancel_and_check(self):
        fake_settings = SimpleNamespace(ai_api_url="https://api.example.com", ai_model="gemini", ai_api_key="secret")
        pipeline = AiPipelineService(FakeWorkspace(), fake_settings)
        self.assertFalse(pipeline.is_cancelled("Task Test 1"))
        pipeline.cancel_task("Task Test 1")
        self.assertTrue(pipeline.is_cancelled("Task Test 1"))
        self.assertTrue(pipeline.is_cancelled("task test 1"))  # case insensitive
        with self.assertRaises(TaskCancelledError):
            pipeline.check_cancelled("Task Test 1")

    def test_task_service_stop_executions_resets_status(self):
        workspace = FakeWorkspace()
        service = TaskService(workspace, 1024, 2048)
        # Bắt đầu execution
        service.tracker.start_executions(
            {"taskNames": ["Task Test 1"], "requestId": "req-123"},
            {"task test 1"},
        )
        self.assertIn("task test 1", service.tracker._running_tasks)

        # Dừng execution
        service.stop_executions({"taskNames": ["Task Test 1"], "requestId": "req-123"})
        self.assertNotIn("task test 1", service.tracker._running_tasks)
        task = workspace.find_task("Task Test 1")
        self.assertEqual(task["Trạng thái"], "Chưa làm")

    def test_task_service_stop_executions_flexible_payload(self):
        workspace = FakeWorkspace()
        workspace.tasks[0]["Trạng thái"] = "Waiting"
        service = TaskService(workspace, 1024, 2048)
        # Hỗ trợ payload dạng {"taskName": "Task Test 1"} không cần requestId
        service.stop_executions({"taskName": "Task Test 1"})
        task = workspace.find_task("Task Test 1")
        self.assertEqual(task["Trạng thái"], "Chưa làm")


if __name__ == "__main__":
    unittest.main()
