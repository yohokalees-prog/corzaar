import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { get, type VerifyResult } from "../src/api";
import { appStyles as s } from "../src/appStyles";
import { VerifyScreen } from "../src/discovery";
import { colors } from "../src/ui";

export default function VerifyRoute() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string }>();
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function lookup(id: string) {
    if (!id) return;
    setBusy(true);
    try { setResult(await get<VerifyResult>(`/certificates/verify/${encodeURIComponent(id)}`)); }
    catch (e: any) { setResult({ valid: false, status: "invalid", certificate_id: id, message: e?.message || "Not found" }); }
    finally { setBusy(false); }
  }
  useEffect(() => { if (params.id) void lookup(String(params.id)); }, [params.id]);

  return <View style={styles.root}>
    <ScrollView contentContainerStyle={[s.scroll, { padding: 16, paddingTop: Math.max(insets.top, 16), paddingBottom: Math.max(insets.bottom + 22, 30) }]}>
      <VerifyScreen onBack={() => router.canGoBack() ? router.back() : router.replace("/")} onLookup={lookup} result={result} busy={busy} initial={params.id ? String(params.id) : ""} />
    </ScrollView>
  </View>;
}

const styles = StyleSheet.create({ root: { flex: 1, backgroundColor: colors.bg } });
