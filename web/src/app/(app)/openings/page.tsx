import { DocumentTitle } from "@/components/document-title";
import { RepertoireView } from "@/components/openings/repertoire-view";

// Мой репертуар — сессия 13.5.
export default function RepertoirePage() {
  return (
    <>
      <DocumentTitle page="repertoire" />
      <RepertoireView />
    </>
  );
}
