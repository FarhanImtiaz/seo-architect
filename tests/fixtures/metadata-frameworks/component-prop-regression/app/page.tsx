const cardProps = { title: "Card", description: "A reusable card, not page metadata" };

function Card() {
  return <div className="card">{cardProps.title}</div>;
}

export default function HomePage() {
  return (
    <main>
      <h1>Home</h1>
      <Card />
    </main>
  );
}
