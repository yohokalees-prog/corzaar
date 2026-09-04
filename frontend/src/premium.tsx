import { Ionicons } from "@expo/vector-icons";
import { Image, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import type { Course, Institute } from "./api";
import { colors, heroArt } from "./ui";

const shadow = Platform.select({
  ios: { shadowColor: "#0F1E33", shadowOpacity: 0.08, shadowRadius: 12, shadowOffset: { width: 0, height: 6 } },
  android: { elevation: 3 },
  default: { boxShadow: "0 6px 12px rgba(15,30,51,0.08)" as any },
}) as any;

const catIconMap: Record<string, keyof typeof Ionicons.glyphMap> = {
  Design: "color-palette-outline",
  Technology: "code-slash-outline",
  Business: "briefcase-outline",
  Marketing: "megaphone-outline",
  "AI / Machine Learning": "hardware-chip-outline",
  "Data Science": "analytics-outline",
  Finance: "cash-outline",
  Language: "language-outline",
  Healthcare: "medkit-outline",
  Engineering: "construct-outline",
};

/** Premium top row: 4 quick action tiles with icon + small badge. */
export function QuickTilesRow({ onCourses, onInstitutes, onOffers, onVerify, offerCount }: {
  onCourses: () => void;
  onInstitutes: () => void;
  onOffers: () => void;
  onVerify: () => void;
  offerCount?: number;
}) {
  const tiles = [
    { key: "courses", label: "Courses", badge: "Discover", tone: "#DDF7EF", icon: "book-outline" as const, ink: colors.green, onPress: onCourses },
    { key: "institutes", label: "Institutes", badge: "Verified", tone: "#E0EAFE", icon: "business-outline" as const, ink: "#3B5F84", onPress: onInstitutes },
    { key: "offers", label: "Offers", badge: offerCount ? `${offerCount} live` : "Save more", tone: "#FEF3C7", icon: "pricetag-outline" as const, ink: "#B45309", onPress: onOffers },
    { key: "verify", label: "Verify", badge: "Free", tone: "#FCE7F3", icon: "shield-checkmark-outline" as const, ink: "#9D174D", onPress: onVerify },
  ];
  return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingHorizontal: 2, paddingVertical: 4 }}>
    {tiles.map(t => <Pressable key={t.key} testID={`qtile-${t.key}`} onPress={t.onPress} style={[styles.tile, shadow]}>
      <View style={styles.tileBadge}><Text style={styles.tileBadgeText}>{t.badge}</Text></View>
      <View style={[styles.tileIcon, { backgroundColor: t.tone }]}><Ionicons name={t.icon} size={22} color={t.ink} /></View>
      <Text style={styles.tileLabel}>{t.label}</Text>
    </Pressable>)}
  </ScrollView>;
}

/** Prominent premium search card — RedBus 'Book bus tickets' vibe. */
export function HomeSearchCard({ search, setSearch, category, setCategory, location, setLocation, categories, locations, onSearch }: {
  search: string;
  setSearch: (v: string) => void;
  category: string;
  setCategory: (v: string) => void;
  location: string;
  setLocation: (v: string) => void;
  categories: string[];
  locations: string[];
  onSearch: () => void;
}) {
  return <View style={[styles.searchCard, shadow]}>
    <View style={styles.searchBanner}><Text style={styles.searchBannerText}>Lowest price guaranteed · Handpicked institutes</Text></View>
    <View style={styles.searchRow}>
      <View style={styles.searchIcon}><Ionicons name="search" size={17} color={colors.green} /></View>
      <TextInput testID="home-search-input" placeholder="Search courses, skills or topics" placeholderTextColor={colors.muted} style={styles.searchField} value={search} onChangeText={setSearch} returnKeyType="search" onSubmitEditing={onSearch} />
    </View>
    <View style={styles.divider} />
    <View style={styles.searchRow}>
      <View style={styles.searchIcon}><Ionicons name="grid-outline" size={17} color={colors.green} /></View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
        {categories.map(cat => <Pressable key={cat} testID={`hc-cat-${cat}`} onPress={() => setCategory(cat)} style={[styles.smallPill, category === cat && styles.smallPillActive]}>
          <Text style={[styles.smallPillText, category === cat && { color: colors.white }]}>{cat}</Text>
        </Pressable>)}
      </ScrollView>
    </View>
    <View style={styles.divider} />
    <View style={styles.searchRow}>
      <View style={styles.searchIcon}><Ionicons name="location-outline" size={17} color={colors.green} /></View>
      <TextInput testID="home-loc-input" placeholder="Any city" placeholderTextColor={colors.muted} style={styles.searchField} value={location} onChangeText={setLocation} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 4 }}>
        {locations.slice(0, 4).map(l => <Pressable key={l} onPress={() => setLocation(l)} style={styles.locChip}><Text style={styles.locChipText}>{l}</Text></Pressable>)}
      </ScrollView>
    </View>
    <Pressable testID="home-search-cta" onPress={onSearch} style={styles.searchCta}>
      <Ionicons name="search" size={17} color={colors.white} />
      <Text style={styles.searchCtaText}>Search courses</Text>
    </Pressable>
  </View>;
}

/** Ranked top-categories horizontal scroll (like RedBus Top Destinations). */
export function TopCategoriesRow({ categories, courses, onPress }: { categories: { key: string; icon: string }[]; courses: Course[]; onPress: (cat: string) => void }) {
  const enriched = categories.slice(0, 6).map((c, index) => {
    const inCat = courses.filter(x => x.category === c.key);
    const minFee = inCat.length ? Math.min(...inCat.map(x => x.fees || 0)) : 0;
    return { ...c, rank: index + 1, count: inCat.length, minFee };
  });
  return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingHorizontal: 2, paddingVertical: 4 }}>
    {enriched.map(c => <Pressable key={c.key} testID={`topcat-${c.key}`} onPress={() => onPress(c.key)} style={[styles.rankCard, shadow]}>
      <Text style={styles.rankNumber}>{c.rank}</Text>
      <View style={{ flex: 1 }}>
        <Text style={styles.rankTitle} numberOfLines={1}>{c.key}</Text>
        <Text style={styles.rankSub}>{c.count ? `From ₹${c.minFee.toLocaleString("en-IN")}` : "Coming soon"}</Text>
      </View>
      <View style={styles.rankBadge}><Text style={styles.rankBadgeText}>{c.count ? "Most booked" : "New"}</Text></View>
    </Pressable>)}
  </ScrollView>;
}

/** Premium full-width course card — RedBus 'bus row' look. */
export function PremiumCourseCard({ course, onPress, saved, onSave }: { course: Course; onPress: () => void; saved?: boolean; onSave?: () => void }) {
  const free = !course.fees || course.fees === 0;
  const hasCert = course.certificate_config?.enabled;
  const catIcon = catIconMap[course.category] || "school-outline";
  const ratingCount = course.reviews_count || course.students || 0;
  const ratingBg = course.rating >= 4.5 ? "#0EA5A0" : course.rating >= 4 ? "#F59E0B" : colors.muted;
  return <Pressable onPress={onPress} testID={`prem-course-${course.id}`} style={({ pressed }) => [styles.premCard, shadow, pressed && { opacity: 0.75 }]}>
    {(hasCert || free) && <View style={styles.premRibbon}><Ionicons name={free ? "sparkles" : "ribbon-outline"} size={11} color={colors.white} /><Text style={styles.premRibbonText}>{free ? "FREE course" : "Certificate included"}</Text></View>}
    <View style={styles.premTopRow}>
      <View style={{ flex: 1 }}>
        <View style={styles.premDurationRow}>
          <Text style={styles.premDuration}>{course.duration}</Text>
          <View style={styles.premTimeDot} />
          <Text style={styles.premMode}>{course.mode}</Text>
        </View>
        <Text style={styles.premMeta}>{ratingCount ? `${ratingCount.toLocaleString("en-IN")} learners` : "New program"}</Text>
      </View>
      <View style={styles.premPriceBlock}>
        {!free && <Text style={styles.premPriceStrike}>₹{Math.round(course.fees * 1.2).toLocaleString("en-IN")}</Text>}
        <Text style={styles.premPriceMain}>{free ? "Free" : `₹${course.fees.toLocaleString("en-IN")}`}</Text>
        <Text style={styles.premPriceSub}>{free ? "Enrol now" : "Onwards"}</Text>
      </View>
    </View>
    <View style={styles.premTitleRow}>
      <View style={styles.premTitleIcon}><Ionicons name={catIcon} size={17} color={colors.green} /></View>
      <View style={{ flex: 1 }}>
        <Text style={styles.premTitle} numberOfLines={2}>{course.title}</Text>
        <Text style={styles.premCat}>{course.category}</Text>
      </View>
      <View style={[styles.ratingPill, { backgroundColor: ratingBg }]}>
        <Ionicons name="star" size={11} color={colors.white} />
        <Text style={styles.ratingPillText}>{course.rating?.toFixed(1) || "—"}</Text>
      </View>
    </View>
    <View style={styles.premChipsRow}>
      {hasCert && <View style={styles.chipMint}><Ionicons name="ribbon-outline" size={11} color={colors.green} /><Text style={styles.chipMintText}>Certificate</Text></View>}
      <View style={styles.chipBlue}><Ionicons name="people-outline" size={11} color="#1E40AF" /><Text style={styles.chipBlueText}>{(course.students || 0).toLocaleString("en-IN")}+ learners</Text></View>
      <View style={styles.chipGray}><Ionicons name="ellipse" size={7} color={colors.orange} /><Text style={styles.chipGrayText}>New batches</Text></View>
      {onSave && <Pressable onPress={onSave} hitSlop={8} style={styles.premSave}><Ionicons name={saved ? "heart" : "heart-outline"} size={16} color={saved ? colors.red : colors.muted} /></Pressable>}
    </View>
    {hasCert && <View style={styles.premReward}>
      <View style={styles.premRewardIcon}><Ionicons name="gift-outline" size={13} color={colors.orange} /></View>
      <Text style={styles.premRewardText}>learnReward</Text>
      <Text style={styles.premRewardBody}>Complete {course.certificate_config?.completion_percent || 100}% to earn a verifiable certificate</Text>
    </View>}
  </Pressable>;
}

/** Institute card — premium look with logo + rating pill + booking chip. */
export function PremiumInstituteCard({ institute, onPress }: { institute: Institute; onPress: () => void }) {
  const ratingBg = institute.rating >= 4.5 ? "#0EA5A0" : "#F59E0B";
  return <Pressable onPress={onPress} testID={`prem-inst-${institute.id}`} style={({ pressed }) => [styles.instCard, shadow, pressed && { opacity: 0.75 }]}>
    <View style={styles.instLogo}><Text style={styles.instLogoText}>{institute.name.charAt(0)}</Text></View>
    <View style={{ flex: 1 }}>
      <Text style={styles.instTitle} numberOfLines={1}>{institute.name}</Text>
      <Text style={styles.instMeta} numberOfLines={1}>{institute.city} · {institute.accreditation}</Text>
      <View style={{ flexDirection: "row", gap: 6, marginTop: 6 }}>
        <View style={[styles.ratingPill, { backgroundColor: ratingBg }]}>
          <Ionicons name="star" size={11} color={colors.white} />
          <Text style={styles.ratingPillText}>{institute.rating?.toFixed(1) || "—"}</Text>
        </View>
        <View style={styles.chipMint}><Text style={styles.chipMintText}>{institute.students} learners</Text></View>
      </View>
    </View>
    <Ionicons name="chevron-forward" size={18} color={colors.muted} />
  </Pressable>;
}

/** Offer strip banner (horizontal). */
export function OffersStrip({ offers, onOpen }: { offers: any[]; onOpen: (o: any) => void }) {
  if (!offers?.length) return null;
  const palette = [["#FEF3C7", "#F59E0B"], ["#DDF7EF", "#0EA5A0"], ["#E0EAFE", "#1E40AF"], ["#FCE7F3", "#9D174D"]];
  return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingHorizontal: 2, paddingVertical: 4 }}>
    {offers.slice(0, 6).map((o, index) => {
      const [bg, ink] = palette[index % palette.length];
      return <Pressable key={o.id || index} testID={`offer-${index}`} onPress={() => onOpen(o)} style={[styles.offerCard, { backgroundColor: bg }, shadow]}>
        <View style={styles.offerBadge}><Text style={styles.offerBadgeText}>Offer</Text></View>
        <Text style={[styles.offerTitle, { color: "#0F1E33" }]} numberOfLines={2}>{o.title || `${o.discount_percent || 20}% off`}</Text>
        <Text style={styles.offerMeta} numberOfLines={2}>{o.subtitle || o.description || "Handpicked deal"}</Text>
        <View style={[styles.offerCode, { borderColor: ink }]}>
          <Ionicons name="pricetag" size={11} color={ink} />
          <Text style={[styles.offerCodeText, { color: ink }]}>{o.code || "SAVE"}</Text>
        </View>
      </Pressable>;
    })}
  </ScrollView>;
}

/** Wrapper hero banner (gradient) with brand + wallet balance. */
export function PremiumHero({ userName, walletBalance }: { userName?: string; walletBalance?: number }) {
  return <View style={[styles.hero, shadow]}>
    <Image source={{ uri: heroArt }} style={StyleSheet.absoluteFill} />
    <View style={styles.heroShade}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
        <View style={styles.heroBrand}><Text style={styles.heroBrandText}>C</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={styles.heroEyebrow}>{userName ? `Hi ${userName.split(" ")[0]}` : "Welcome to CORZAAR"}</Text>
          <Text style={styles.heroTitle}>Find your next skill.</Text>
        </View>
        {typeof walletBalance === "number" && <View style={styles.walletChip}>
          <Ionicons name="wallet-outline" size={13} color={colors.green} />
          <Text style={styles.walletChipText}>₹{walletBalance.toLocaleString("en-IN")}</Text>
        </View>}
      </View>
    </View>
  </View>;
}

// -----------------------------------------------------------------------------
export const styles = StyleSheet.create({
  // top tiles
  tile: { width: 96, height: 106, borderRadius: 16, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line, padding: 10, alignItems: "flex-start", justifyContent: "space-between" },
  tileBadge: { alignSelf: "flex-start", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, backgroundColor: "#DDF7EF" },
  tileBadgeText: { color: colors.green, fontSize: 9, fontWeight: "800", letterSpacing: 0.3 },
  tileIcon: { width: 38, height: 38, borderRadius: 12, alignItems: "center", justifyContent: "center", marginTop: 4 },
  tileLabel: { color: colors.ink, fontSize: 13, fontWeight: "800" },

  // search card
  searchCard: { borderRadius: 20, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line, overflow: "hidden" },
  searchBanner: { backgroundColor: "#1E3A5F", paddingVertical: 10, alignItems: "center" },
  searchBannerText: { color: colors.white, fontSize: 11, fontWeight: "800", letterSpacing: 0.4 },
  searchRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, minHeight: 54 },
  searchIcon: { width: 30, height: 30, borderRadius: 9, backgroundColor: colors.mint, alignItems: "center", justifyContent: "center" },
  searchField: { flex: 1, color: colors.ink, fontSize: 14, paddingVertical: 12 },
  divider: { height: 1, backgroundColor: colors.line, marginLeft: 60 },
  smallPill: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: colors.soft, minHeight: 30, alignItems: "center", justifyContent: "center" },
  smallPillActive: { backgroundColor: colors.green },
  smallPillText: { color: colors.green, fontSize: 12, fontWeight: "700" },
  locChip: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, backgroundColor: "#FCE7F3", minHeight: 24, alignItems: "center", justifyContent: "center" },
  locChipText: { color: "#9D174D", fontSize: 11, fontWeight: "700" },
  searchCta: { margin: 14, minHeight: 50, borderRadius: 14, backgroundColor: colors.red, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8 },
  searchCtaText: { color: colors.white, fontSize: 15, fontWeight: "800", letterSpacing: 0.3 },

  // ranked top categories
  rankCard: { width: 168, minHeight: 90, borderRadius: 16, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line, padding: 12, flexDirection: "row", alignItems: "center", gap: 10, overflow: "hidden" },
  rankNumber: { fontSize: 46, fontWeight: "900", color: "#F1F5F9", position: "absolute", right: 8, top: 4, letterSpacing: -1 },
  rankTitle: { color: colors.ink, fontSize: 15, fontWeight: "800" },
  rankSub: { color: colors.muted, fontSize: 12, marginTop: 3 },
  rankBadge: { position: "absolute", left: 12, bottom: 8, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, backgroundColor: "#FEF3C7" },
  rankBadgeText: { color: "#B45309", fontSize: 10, fontWeight: "800" },

  // premium course card
  premCard: { borderRadius: 18, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line, padding: 16, gap: 10, overflow: "hidden" },
  premRibbon: { alignSelf: "flex-end", position: "absolute", right: 0, top: 0, backgroundColor: colors.green, paddingHorizontal: 12, paddingVertical: 5, borderBottomLeftRadius: 12, flexDirection: "row", alignItems: "center", gap: 5 },
  premRibbonText: { color: colors.white, fontSize: 10, fontWeight: "800", letterSpacing: 0.3 },
  premTopRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginTop: 8 },
  premDurationRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  premDuration: { color: colors.ink, fontSize: 17, fontWeight: "800", letterSpacing: -0.3 },
  premTimeDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: colors.muted },
  premMode: { color: colors.ink, fontSize: 14, fontWeight: "700" },
  premMeta: { color: colors.orange, fontSize: 12, marginTop: 4, fontWeight: "600" },
  premPriceBlock: { alignItems: "flex-end" },
  premPriceStrike: { color: colors.muted, fontSize: 12, textDecorationLine: "line-through" },
  premPriceMain: { color: colors.ink, fontSize: 20, fontWeight: "900", letterSpacing: -0.5 },
  premPriceSub: { color: colors.muted, fontSize: 11, marginTop: 1 },
  premTitleRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  premTitleIcon: { width: 34, height: 34, borderRadius: 10, backgroundColor: colors.mint, alignItems: "center", justifyContent: "center" },
  premTitle: { color: colors.ink, fontSize: 15, fontWeight: "800", lineHeight: 20 },
  premCat: { color: colors.muted, fontSize: 12, marginTop: 2 },
  ratingPill: { flexDirection: "row", alignItems: "center", gap: 3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  ratingPillText: { color: colors.white, fontSize: 12, fontWeight: "800" },
  premChipsRow: { flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 6 },
  chipMint: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, backgroundColor: "#E7F5EE" },
  chipMintText: { color: colors.green, fontSize: 11, fontWeight: "700" },
  chipBlue: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, backgroundColor: "#E0EAFE" },
  chipBlueText: { color: "#1E40AF", fontSize: 11, fontWeight: "700" },
  chipGray: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, backgroundColor: colors.soft },
  chipGrayText: { color: colors.ink, fontSize: 11, fontWeight: "700" },
  premSave: { marginLeft: "auto", padding: 4 },
  premReward: { flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: "#FFF7EA", padding: 10, borderRadius: 12, marginTop: 2 },
  premRewardIcon: { width: 26, height: 26, borderRadius: 8, backgroundColor: "#FEF3C7", alignItems: "center", justifyContent: "center" },
  premRewardText: { color: colors.orange, fontSize: 12, fontWeight: "800" },
  premRewardBody: { color: colors.muted, fontSize: 11, flex: 1 },

  // institute
  instCard: { flexDirection: "row", alignItems: "center", gap: 12, padding: 14, borderRadius: 16, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line },
  instLogo: { width: 50, height: 50, borderRadius: 15, backgroundColor: colors.mint, alignItems: "center", justifyContent: "center" },
  instLogoText: { color: colors.green, fontSize: 21, fontWeight: "900" },
  instTitle: { color: colors.ink, fontSize: 15, fontWeight: "800" },
  instMeta: { color: colors.muted, fontSize: 12, marginTop: 3 },

  // offers
  offerCard: { width: 220, minHeight: 130, borderRadius: 18, padding: 14, gap: 6, position: "relative" },
  offerBadge: { alignSelf: "flex-start", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, backgroundColor: "#0F1E33" },
  offerBadgeText: { color: colors.white, fontSize: 10, fontWeight: "800" },
  offerTitle: { fontSize: 16, fontWeight: "800", marginTop: 6, lineHeight: 20 },
  offerMeta: { color: colors.muted, fontSize: 11, lineHeight: 15 },
  offerCode: { alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 5, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, borderWidth: 1, borderStyle: "dashed", backgroundColor: colors.white, marginTop: 6 },
  offerCodeText: { fontSize: 11, fontWeight: "800" },

  // hero
  hero: { height: 130, borderRadius: 20, overflow: "hidden" },
  heroShade: { flex: 1, padding: 18, justifyContent: "center", backgroundColor: "#0F1E3399" },
  heroBrand: { width: 40, height: 40, borderRadius: 12, backgroundColor: colors.white, alignItems: "center", justifyContent: "center" },
  heroBrandText: { color: colors.green, fontSize: 20, fontWeight: "900" },
  heroEyebrow: { color: "#DFF5EB", fontSize: 11, fontWeight: "800", letterSpacing: 0.6 },
  heroTitle: { color: colors.white, fontSize: 20, fontWeight: "800", marginTop: 3 },
  walletChip: { flexDirection: "row", gap: 5, alignItems: "center", backgroundColor: colors.white, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999 },
  walletChipText: { color: colors.green, fontSize: 13, fontWeight: "800" },
});
