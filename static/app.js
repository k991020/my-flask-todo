const listEl = document.getElementById("todo-list");
const formEl = document.getElementById("todo-form");
const inputEl = document.getElementById("todo-input");
const filterBtns = document.querySelectorAll(".filter-btn");

let currentFilter = "all";

async function fetchTodos() {
  const res = await fetch(`/api/todos?filter=${currentFilter}`);

  // 로그인 만료/비로그인 상태면 로그인 페이지로 이동
  if (res.status === 401) {
    window.location.href = "/login";
    return;
  }

  const todos = await res.json();
  render(todos);
}


function setActiveFilterUI() {
  filterBtns.forEach((b) => {
    b.classList.toggle("active", b.dataset.filter === currentFilter);
  });
}

function render(todos) {
  listEl.innerHTML = "";

  for (const t of todos) {
    const li = document.createElement("li");
    li.className = "todo";

    const left = document.createElement("div");
    left.className = "left";

    const toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.className = "toggle";
    toggleBtn.textContent = t.done ? "✓" : "";
    toggleBtn.style.color = t.done ? "#34c759" : "#1d1d1f";

    toggleBtn.addEventListener("click", async () => {
      await toggleTodo(t.id);
      await fetchTodos();
    });

    const span = document.createElement("span");
    span.textContent = t.title;
    span.className = t.done ? "done" : "";

    left.appendChild(toggleBtn);
    left.appendChild(span);

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "delete";
    delBtn.textContent = "삭제";
    delBtn.addEventListener("click", async () => {
      const ok = confirm("삭제할까?");
      if (!ok) return;
      await deleteTodo(t.id);
      await fetchTodos();
    });

    li.appendChild(left);
    li.appendChild(delBtn);
    listEl.appendChild(li);
  }
}

async function addTodo(title) {
  const res = await fetch("/api/todos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.error || "추가 실패");
    return;
  }

  inputEl.value = "";
  await fetchTodos();
}

async function toggleTodo(id) {
  const res = await fetch(`/api/todos/${id}`, { method: "PATCH" });
  if (!res.ok) alert("토글 실패");
}

async function deleteTodo(id) {
  const res = await fetch(`/api/todos/${id}`, { method: "DELETE" });

  if (res.status === 401) {
    window.location.href = "/login";
    return;
  }

  if (!res.ok) {
    const body = await res.text();
    alert(`삭제 실패: ${res.status}\n${body}`);
    return;
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const title = inputEl.value.trim();
  if (!title) return;
  addTodo(title);
});

filterBtns.forEach((b) => {
  b.addEventListener("click", async () => {
    currentFilter = b.dataset.filter;
    setActiveFilterUI();
    await fetchTodos();
  });
});

setActiveFilterUI();
fetchTodos();
