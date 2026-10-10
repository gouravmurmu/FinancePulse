import { AssetView } from "@/components/asset/asset-view";

export default async function AssetPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AssetView id={decodeURIComponent(id)} />;
}
