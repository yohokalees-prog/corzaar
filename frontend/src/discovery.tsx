import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import { Modal, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import type { DiscoveryCategory, DurationBucket } from "./api";
import { appStyles as s } from "./appStyles";
import { Button, Icon, colors, styles as uiBase } from "./ui";

const ui: any = { ...uiBase, smallMuted: { color: colors.muted, fontSize: 12, lineHeight: 18 } };

export type FilterState = {
  category: string;
  location: string;
  duration: string;
  min_rating: string;
  price_min: string;
  price_max: string;
  mode: string;
  free_only: boolean;
  has_certificate: boolean;
  sort: string;
};

export const emptyFilters: FilterState = {
  category: "All",
  location: "",
  duration: "all",
  min_rating: "",
  price_min: "",
  price_max: "",
  mode: "",
  free_only: false,
  has_certificate: false,
  sort: "recommended",
};

/** Encodes filter state to /courses querystring. */
export function filterQuery(f: FilterState, q: string): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (f.category && f.category !== "All") params.set("category", f.category);
  if (f.location) params.set("location", f.location);
  if (f.duration && f.duration !== "all") params.set("duration", f.duration);
  if (f.min_rating) params.set("min_rating", f.min_rating);
  if (f.price_min) params.set("price_min", f.price_min);
  if (f.price_max) params.set("price_max", f.price_max);
  if (f.mode) params.set("mode", f.mode);
  if (f.free_only) params.set("free_only", "true");
  if (f.has_certificate) params.set("has_certificate", "true");
  if (f.sort && f.sort !== "recommended") params.set("sort", f.sort);
  return params.toString();
}

/** Returns array of active-filter chips (label + reset). */
export function activeFilterChips(f: FilterState): { key: keyof FilterState; label: string }[] {
  const chips: { key: keyof FilterState; label: string }[] = [];
  if (f.category !== "All") chips.push({ key: "category", label: f.category });
  if (f.location) chips.push({ key: "location", label: f.location });
  if (f.duration !== "all") chips.push({ key: "duration", label: durationLabel(f.duration) });
  if (f.min_rating) chips.push({ key: "min_rating", label: `${f.min_rating}★ +` });
  if (f.price_min || f.price_max) chips.push({ key: "price_min", label: `₹${f.price_min || 0} – ₹${f.price_max || "∞"}` });
  if (f.mode) chips.push({ key: "mode", label: f.mode });
  if (f.free_only) chips.push({ key: "free_only", label: "Free only" });
  if (f.has_certificate) chips.push({ key: "has_certificate", label: "Certificate" });
  return chips;
}

function durationLabel(key: string): string {
  return ({ under_1m: "< 1 month", "1_3m": "1–3 months", "3_6m": "3–6 months", "6_12m": "6–12 months", over_1y: "1+ year" } as any)[key] || key;
}

export function DiscoveryPanel({ categories, locations, activeTab, onTab, onCategory, onLocation, onOpenFilters, onSearch }: {
  categories: DiscoveryCategory[];
  locations: string[];
  activeTab: "courses" | "institutes";
  onTab: (t: "courses" | "institutes") => void;
  onCategory: (cat: string) => void;
  onLocation: (loc: string) => void;
  onOpenFilters: () => void;
  onSearch: () => void;
}) {
  return <View style={{ backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line, borderRadius: 20, padding: 14, gap: 12 }}>
    <View style={{ flexDirection: "row", gap: 6, backgroundColor: colors.soft, borderRadius: 12, padding: 4 }}>
      {(["courses", "institutes"] as const).map(t => <Pressable key={t} testID={`disc-tab-${t}`} onPress={() => onTab(t)} style={{ flex: 1, minHeight: 42, borderRadius: 9, alignItems: "center", justifyContent: "center", backgroundColor: activeTab === t ? colors.green : "transparent", flexDirection: "row", gap: 6 }}>
        <Icon name={t === "courses" ? "book-outline" : "business-outline"} size={16} color={activeTab === t ? colors.white : colors.green} />
        <Text style={{ color: activeTab === t ? colors.white : colors.green, fontWeight: "800", fontSize: 13 }}>{t === "courses" ? "Courses" : "Institutes"}</Text>
      </Pressable>)}
    </View>
    <View style={{ flexDirection: "row", gap: 8 }}>
      <Pressable testID="disc-search-cta" onPress={onSearch} style={{ flex: 1, minHeight: 46, borderRadius: 12, backgroundColor: colors.green, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8 }}>
        <Icon name="search" size={17} color={colors.white} />
        <Text style={{ color: colors.white, fontWeight: "800" }}>Explore {activeTab === "courses" ? "courses" : "institutes"}</Text>
      </Pressable>
      <Pressable testID="disc-filter" onPress={onOpenFilters} style={{ minHeight: 46, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 6 }}>
        <Icon name="options-outline" size={17} color={colors.green} />
        <Text style={{ color: colors.green, fontWeight: "800" }}>Filters</Text>
      </Pressable>
    </View>
    <Text style={{ color: colors.ink, fontSize: 12, fontWeight: "800", letterSpacing: 1 }}>BROWSE BY CATEGORY</Text>
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {categories.slice(0, 8).map(c => <Pressable key={c.key} testID={`disc-cat-${c.key}`} onPress={() => onCategory(c.key)} style={{ flexBasis: "48%", flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderWidth: 1, borderColor: colors.line, borderRadius: 12, backgroundColor: colors.soft }}>
        <View style={{ width: 32, height: 32, borderRadius: 10, backgroundColor: colors.mint, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name={(c.icon as any) || "school-outline"} size={17} color={colors.green} />
        </View>
        <Text style={{ color: colors.ink, fontWeight: "700", fontSize: 12, flex: 1 }} numberOfLines={2}>{c.key}</Text>
      </Pressable>)}
    </View>
    {locations.length > 0 && <>
      <Text style={{ color: colors.ink, fontSize: 12, fontWeight: "800", letterSpacing: 1 }}>POPULAR LOCATIONS</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        {locations.map(loc => <Pressable key={loc} testID={`disc-loc-${loc}`} onPress={() => onLocation(loc)} style={[s.pill, { flexShrink: 0, flexDirection: "row" }]}>
          <Icon name="location-outline" size={14} color={colors.green} />
          <Text style={s.pillText}>{loc}</Text>
        </Pressable>)}
      </ScrollView>
    </>}
  </View>;
}

export function FilterModal({ visible, filters, setFilters, onApply, onClose, onReset, categories, locations, durations }: {
  visible: boolean;
  filters: FilterState;
  setFilters: (f: FilterState) => void;
  onApply: () => void;
  onClose: () => void;
  onReset: () => void;
  categories: string[];
  locations: string[];
  durations: DurationBucket[];
}) {
  const modes = ["Online", "Offline", "Hybrid", "Self-paced", "Live online"];
  const ratings = ["4.5", "4.0", "3.5"];
  const sorts = [
    { key: "recommended", label: "Recommended" },
    { key: "newest", label: "Newest" },
    { key: "price_asc", label: "Price ↑" },
    { key: "price_desc", label: "Price ↓" },
    { key: "students", label: "Most popular" },
  ];
  return <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
    <View style={s.modalWrap}>
      <View style={[s.modal, { maxHeight: "92%" }]}>
        <View style={s.handle} />
        <View style={s.modalHeader}>
          <Text style={ui.h2}>Filter courses</Text>
          <Pressable onPress={onClose} style={s.iconButton}><Icon name="close" size={20} /></Pressable>
        </View>
        <ScrollView style={{ maxHeight: 520 }}>
          <Text style={s.label}>Category</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 4 }}>
            {categories.map(cat => <Pressable key={cat} onPress={() => setFilters({ ...filters, category: cat })} style={[s.pill, filters.category === cat && s.activePill, { flexShrink: 0 }]}>
              <Text style={[s.pillText, filters.category === cat && { color: colors.white }]}>{cat}</Text>
            </Pressable>)}
          </ScrollView>

          <Text style={s.label}>Location</Text>
          <TextInput testID="filter-location" style={s.formInput} value={filters.location} onChangeText={location => setFilters({ ...filters, location })} placeholder="Any city" placeholderTextColor={colors.muted} />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingVertical: 2 }}>
            {locations.map(loc => <Pressable key={loc} onPress={() => setFilters({ ...filters, location: loc })} style={[s.pill, filters.location === loc && s.activePill, { flexShrink: 0 }]}>
              <Text style={[s.pillText, filters.location === loc && { color: colors.white }]}>{loc}</Text>
            </Pressable>)}
          </ScrollView>

          <Text style={s.label}>Duration</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
            <Pressable onPress={() => setFilters({ ...filters, duration: "all" })} style={[s.pill, filters.duration === "all" && s.activePill]}>
              <Text style={[s.pillText, filters.duration === "all" && { color: colors.white }]}>Any</Text>
            </Pressable>
            {durations.map(d => <Pressable key={d.key} onPress={() => setFilters({ ...filters, duration: d.key })} style={[s.pill, filters.duration === d.key && s.activePill]}>
              <Text style={[s.pillText, filters.duration === d.key && { color: colors.white }]}>{d.label}</Text>
            </Pressable>)}
          </View>

          <Text style={s.label}>Price range (₹)</Text>
          <View style={{ flexDirection: "row", gap: 8 }}>
            <TextInput testID="filter-price-min" style={[s.formInput, { flex: 1 }]} value={filters.price_min} onChangeText={price_min => setFilters({ ...filters, price_min })} placeholder="Min" placeholderTextColor={colors.muted} keyboardType="numeric" />
            <TextInput testID="filter-price-max" style={[s.formInput, { flex: 1 }]} value={filters.price_max} onChangeText={price_max => setFilters({ ...filters, price_max })} placeholder="Max" placeholderTextColor={colors.muted} keyboardType="numeric" />
          </View>
          <Pressable onPress={() => setFilters({ ...filters, free_only: !filters.free_only })} style={{ flexDirection: "row", gap: 8, alignItems: "center", padding: 6 }}>
            <Icon name={filters.free_only ? "checkbox" : "square-outline"} size={20} color={filters.free_only ? colors.green : colors.muted} />
            <Text style={s.body}>Free courses only</Text>
          </Pressable>

          <Text style={s.label}>Minimum rating</Text>
          <View style={{ flexDirection: "row", gap: 6, marginTop: 4 }}>
            <Pressable onPress={() => setFilters({ ...filters, min_rating: "" })} style={[s.pill, !filters.min_rating && s.activePill]}>
              <Text style={[s.pillText, !filters.min_rating && { color: colors.white }]}>Any</Text>
            </Pressable>
            {ratings.map(r => <Pressable key={r} onPress={() => setFilters({ ...filters, min_rating: r })} style={[s.pill, filters.min_rating === r && s.activePill]}>
              <Text style={[s.pillText, filters.min_rating === r && { color: colors.white }]}>{r}★ +</Text>
            </Pressable>)}
          </View>

          <Text style={s.label}>Mode</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingVertical: 4 }}>
            <Pressable onPress={() => setFilters({ ...filters, mode: "" })} style={[s.pill, !filters.mode && s.activePill, { flexShrink: 0 }]}>
              <Text style={[s.pillText, !filters.mode && { color: colors.white }]}>Any</Text>
            </Pressable>
            {modes.map(m => <Pressable key={m} onPress={() => setFilters({ ...filters, mode: m })} style={[s.pill, filters.mode === m && s.activePill, { flexShrink: 0 }]}>
              <Text style={[s.pillText, filters.mode === m && { color: colors.white }]}>{m}</Text>
            </Pressable>)}
          </ScrollView>

          <Pressable onPress={() => setFilters({ ...filters, has_certificate: !filters.has_certificate })} style={{ flexDirection: "row", gap: 8, alignItems: "center", padding: 6, marginTop: 4 }}>
            <Icon name={filters.has_certificate ? "checkbox" : "square-outline"} size={20} color={filters.has_certificate ? colors.green : colors.muted} />
            <Text style={s.body}>Certificate available</Text>
          </Pressable>

          <Text style={s.label}>Sort by</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingVertical: 4 }}>
            {sorts.map(sO => <Pressable key={sO.key} onPress={() => setFilters({ ...filters, sort: sO.key })} style={[s.pill, filters.sort === sO.key && s.activePill, { flexShrink: 0 }]}>
              <Text style={[s.pillText, filters.sort === sO.key && { color: colors.white }]}>{sO.label}</Text>
            </Pressable>)}
          </ScrollView>
        </ScrollView>
        <View style={{ flexDirection: "row", gap: 8, paddingTop: 4 }}>
          <Button testID="filter-reset" label="Reset all" secondary onPress={onReset} />
          <View style={{ flex: 1 }}><Button testID="filter-apply" label="Apply filters" onPress={onApply} /></View>
        </View>
      </View>
    </View>
  </Modal>;
}

/** Small chip strip shown above result list. */
export function ActiveFilterChips({ filters, onRemove, onClearAll }: { filters: FilterState; onRemove: (k: keyof FilterState) => void; onClearAll: () => void }) {
  const chips = activeFilterChips(filters);
  if (!chips.length) return null;
  return <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, alignItems: "center", marginTop: 8 }}>
    {chips.map(chip => <Pressable key={chip.key} onPress={() => onRemove(chip.key)} style={{ flexDirection: "row", gap: 6, alignItems: "center", paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, backgroundColor: colors.mint }}>
      <Text style={{ color: colors.green, fontSize: 12, fontWeight: "700" }}>{chip.label}</Text>
      <Icon name="close" size={12} color={colors.green} />
    </Pressable>)}
    <Pressable onPress={onClearAll} style={{ paddingHorizontal: 8, paddingVertical: 6 }}>
      <Text style={{ color: colors.orange, fontWeight: "800", fontSize: 12 }}>Clear all</Text>
    </Pressable>
  </View>;
}

/** In-app verify screen (searchable). */
export function VerifyScreen({ onBack, onLookup, result, busy, initial }: { onBack: () => void; onLookup: (id: string) => void; result: any | null; busy: boolean; initial?: string }) {
  const [id, setId] = useState(initial || "");
  return <View style={{ gap: 12 }}>
    <View style={s.header}>
      <Pressable onPress={onBack} style={s.iconButton}><Icon name="arrow-back" size={21} /></Pressable>
      <Text style={s.headerTitle}>Verify certificate</Text>
      <View style={{ width: 26 }} />
    </View>
    <Text style={s.h1}>Verify a CORZAAR certificate.</Text>
    <Text style={s.body}>Paste the certificate ID (e.g. CORZAAR-INST-CRSE-A1B2C3D4) to confirm authenticity.</Text>
    <TextInput testID="verify-input" style={s.formInput} value={id} onChangeText={setId} placeholder="CORZAAR-..." placeholderTextColor={colors.muted} autoCapitalize="characters" autoCorrect={false} />
    <Button testID="verify-submit" label={busy ? "Verifying…" : "Verify certificate"} onPress={() => onLookup(id.trim())} icon="shield-checkmark-outline" />
    {result && <View style={[s.info, { borderColor: result.valid ? colors.orange : colors.red, borderWidth: 1 }]}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <Icon name={result.valid ? "checkmark-circle" : "close-circle"} size={22} color={result.valid ? colors.orange : colors.red} />
        <Text style={{ fontSize: 16, fontWeight: "800", color: result.valid ? colors.green : colors.red }}>
          {result.valid ? "Valid certificate" : (result.status === "pending_approval" ? "Pending approval" : "Not verified")}
        </Text>
      </View>
      {result.student_name && <Text style={ui.cardTitle}>{result.student_name}</Text>}
      {result.course_title && <Text style={ui.smallMuted}>{result.course_title}</Text>}
      {result.institute_name && <Text style={ui.smallMuted}>Issued by {result.institute_name}</Text>}
      {result.issue_date && <Text style={ui.smallMuted}>On {String(result.issue_date).slice(0, 10)}</Text>}
      <Text style={{ color: colors.muted, fontSize: 11, marginTop: 4 }}>{result.certificate_id}</Text>
      {!result.valid && result.message && <Text style={{ color: colors.red, fontSize: 12 }}>{result.message}</Text>}
    </View>}
  </View>;
}
