import { MoveoutDocument } from "@/components/MoveoutDocument";
import { Topbar } from "@/components/Topbar";

export default async function MoveoutPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <Topbar current="moveout" />
      <MoveoutDocument id={id} />
    </>
  );
}
