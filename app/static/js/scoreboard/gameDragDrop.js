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
  // Deferred so the browser snapshots the drag-ghost image at full opacity
  // before this class (and its CSS-driven dimming) applies to the source
  // element. Using a real class - not an inline style - is what lets
  // getDragAfterElement's `:not(.dragging)` selector below actually exclude
  // the item being dragged from its own position calculation; without it,
  // the dragged item kept comparing against its own constantly-shifting
  // bounding box as it was repositioned, which is what made dragging further
  // down the list feel increasingly slow and jumpy.
  setTimeout(() => draggedItem.classList.add("dragging"), 0);
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
  // dragend (below) fires right after drop for every in-list reorder and
  // already does the cleanup + order save - handling it here too just meant
  // every reorder fired two identical save requests.
}

function handleDragEnd() {
  if (draggedItem) {
    draggedItem.classList.remove("dragging");
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
      body: JSON.stringify({ roomID, games: updatedOrder }),
    });
  } catch (error) {
    console.error("Error updating game order:", error);
  }
}

attachDragAndDrop();
