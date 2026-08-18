// gameDragDrop.js
let draggedItem = null;

export function attachDragAndDrop() {
  const gameList = document.getElementById("game-list");
  const draggableItems = document.querySelectorAll(".game-list-card.draggable");

  // 🔥 Remove previous event listeners before attaching new ones
  draggableItems.forEach((item) => {
    item.removeEventListener("dragstart", handleDragStart);
    item.removeEventListener("dragover", handleDragOver);
    item.removeEventListener("drop", handleDrop);
    item.removeEventListener("dragend", handleDragEnd);
  });

  // 🔥 Attach fresh event listeners
  draggableItems.forEach((item) => {
    item.addEventListener("dragstart", handleDragStart);
    item.addEventListener("dragover", (e) => handleDragOver(e, gameList));
    item.addEventListener("drop", handleDrop);
    item.addEventListener("dragend", handleDragEnd);
  });
}

// Event Handlers (Moved outside for cleaner code)
function handleDragStart(e) {
  draggedItem = e.target;
  e.dataTransfer.effectAllowed = "move";
  setTimeout(() => (draggedItem.style.opacity = "0.5"), 0);
}

function handleDragOver(e, container) {
  e.preventDefault();
  const afterElement = getDragAfterElement(container, e.clientY);
  if (afterElement == null) {
    container.appendChild(draggedItem);
  } else if (afterElement instanceof Node && draggedItem !== afterElement) {
    container.insertBefore(draggedItem, afterElement);
  }
}

function handleDrop() {
  if (draggedItem) {
    draggedItem.style.opacity = "1";
    updateGameOrder();
  }
}

function handleDragEnd() {
  if (draggedItem) {
    draggedItem.style.opacity = "1";
    updateGameOrder();
    draggedItem = null;
  }
}

function getDragAfterElement(container, y) {
  const elements = [...container.querySelectorAll(".draggable:not(.dragging)")];

  return (
    elements.reduce(
      (closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
          return { offset, element: child };
        } else {
          return closest;
        }
      },
      { offset: Number.NEGATIVE_INFINITY, element: null }
    ).element || null
  );
}

async function updateGameOrder() {
  const updatedOrder = [
    ...document.querySelectorAll(".game-list-card.draggable"),
  ].map((game, index) => ({
    game_id: game.dataset.id,
    game_sort: index + 1,
  }));

  try {
    await fetch(`/api/v1/games/update-game-order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updatedOrder),
    });
  } catch (error) {
    console.error("Error updating game order:", error);
  }
}

attachDragAndDrop();
