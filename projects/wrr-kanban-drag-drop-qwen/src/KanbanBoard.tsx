import React, { useState } from "react";

interface Card {
  id: string;
  title: string;
  status: "todo" | "doing" | "done";
}

const KanbanBoard: React.FC = () => {
  const [cards, setCards] = useState<Card[]>([]);
  // TODO: implement drag and drop between columns
  // TODO: implement status auto-update on drop
  return <div>Kanban Board - TODO: implement</div>;
};

export default KanbanBoard;
