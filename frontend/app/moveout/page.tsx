import { DocFooter } from "@/components/DocFooter";
import { MoveoutIntake } from "@/components/MoveoutIntake";
import { Toc } from "@/components/Toc";
import { Topbar } from "@/components/Topbar";

const TOC = [{ id: "evidence", title: "Agreement and evidence" }];

export default function MoveoutStart() {
  return (
    <>
      <Topbar current="moveout" />
      <main className="doc">
        <Toc items={TOC} />
        <article className="doc-main">
          <p className="kicker">Move-out</p>
          <h1 className="doc-title">Check the landlord&apos;s deductions before you accept them</h1>
          <p className="doc-subtitle">
            Dhara compares each claimed deduction with your agreement and the dated move-in checklist, drafts a challenge for the ones that do not
            hold, and shows the formal route if the deposit is not returned.
          </p>
          <MoveoutIntake />
          <DocFooter />
        </article>
      </main>
    </>
  );
}
