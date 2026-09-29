export async function generateMetadata({ params }) {
  return { title: `Item ${params.id}` };
}

export default function Page() {
  return <main><h1>Item</h1></main>;
}
