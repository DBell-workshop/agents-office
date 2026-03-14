const state = {
  courseId: null,
  attemptId: null,
  comparisonTaskId: null,
  lastTaskId: null,
};

function setOutput(data) {
  document.getElementById("output").textContent = JSON.stringify(data, null, 2);
}

async function post(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Request failed: ${response.status}`);
  }
  return await response.json();
}

async function get(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const err = await response.text();
    throw new Error(err || `Request failed: ${response.status}`);
  }
  return await response.json();
}

function bindEvents() {
  document.getElementById("btn-create-course").addEventListener("click", async () => {
    try {
      const required = document.getElementById("tr-required").value
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
      const body = {
        product_id: document.getElementById("tr-product-id").value,
        product_name: document.getElementById("tr-product-name").value,
        objective: document.getElementById("tr-objective").value,
        required_points: required,
        product_facts: {
          installments: document.getElementById("tr-installments").value,
        },
      };
      const data = await post("/api/v1/training/courses", body);
      state.courseId = data.data.course_id;
      setOutput(data);
    } catch (err) {
      setOutput({ error: String(err) });
    }
  });

  document.getElementById("btn-generate-content").addEventListener("click", async () => {
    try {
      if (!state.courseId) throw new Error("Create course first");
      const data = await post(`/api/v1/training/courses/${state.courseId}:generate-content`, {
        script_style: "natural",
        scene: "in_store",
        language: "zh-CN",
      });
      state.lastTaskId = data.data.task_id;
      document.getElementById("task-id").value = state.lastTaskId;
      setOutput(data);
    } catch (err) {
      setOutput({ error: String(err) });
    }
  });

  document.getElementById("btn-create-attempt").addEventListener("click", async () => {
    try {
      if (!state.courseId) throw new Error("Create course first");
      const data = await post("/api/v1/training/attempts", {
        course_id: state.courseId,
        user_id: document.getElementById("tr-user").value,
        mock_transcript: document.getElementById("tr-transcript").value,
      });
      state.attemptId = data.data.attempt_id;
      setOutput(data);
    } catch (err) {
      setOutput({ error: String(err) });
    }
  });

  document.getElementById("btn-evaluate-attempt").addEventListener("click", async () => {
    try {
      if (!state.attemptId) throw new Error("Submit attempt first");
      const data = await post(`/api/v1/training/attempts/${state.attemptId}:evaluate`, {
        rubric_version: "v1",
      });
      state.lastTaskId = data.data.task_id;
      document.getElementById("task-id").value = state.lastTaskId;
      setOutput(data);
    } catch (err) {
      setOutput({ error: String(err) });
    }
  });

  document.getElementById("btn-create-comparison").addEventListener("click", async () => {
    try {
      const data = await post("/api/v1/comparison/tasks", {
        source_product_id: document.getElementById("cp-source-id").value,
        source_product_name: document.getElementById("cp-source-name").value,
        targets: [
          { platform: "jd", url: document.getElementById("cp-jd-url").value },
          { platform: "taobao", url: document.getElementById("cp-taobao-url").value },
        ],
      });
      state.comparisonTaskId = data.data.comparison_task_id;
      setOutput(data);
    } catch (err) {
      setOutput({ error: String(err) });
    }
  });

  document.getElementById("btn-run-comparison").addEventListener("click", async () => {
    try {
      if (!state.comparisonTaskId) throw new Error("Create comparison task first");
      const data = await post(`/api/v1/comparison/tasks/${state.comparisonTaskId}:run`, {
        template_version: "default_v1",
      });
      state.lastTaskId = data.data.task_id;
      document.getElementById("task-id").value = state.lastTaskId;
      setOutput(data);
    } catch (err) {
      setOutput({ error: String(err) });
    }
  });

  document.getElementById("btn-check-task").addEventListener("click", async () => {
    try {
      const taskId = document.getElementById("task-id").value.trim();
      if (!taskId) throw new Error("Input task_id first");
      const data = await get(`/api/v1/tasks/${taskId}`);
      setOutput(data);
    } catch (err) {
      setOutput({ error: String(err) });
    }
  });
}

bindEvents();
