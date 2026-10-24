import { ReviewDocument } from "@/components/ReviewDocument";
import { Topbar } from "@/components/Topbar";

export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <Topbar current="review" />
      <ReviewDocument id={id} />
    </>
  );
}
