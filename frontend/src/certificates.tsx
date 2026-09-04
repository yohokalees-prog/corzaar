import { useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { get, post, put, remove, type CertConfig, type CertTemplate, type Certificate, type Course } from "./api";
import { appStyles as s } from "./appStyles";
import { Button, EmptyState, Icon, SectionTitle, Tag, colors, styles as uiBase } from "./ui";

const ui: any = { ...uiBase, smallMuted: { color: colors.muted, fontSize: 12, lineHeight: 18 } };

const STYLE_OPTIONS: { key: "classic" | "modern" | "bold"; label: string; accent: string }[] = [
  { key: "classic", label: "Classic Navy", accent: "#1E3A5F" },
  { key: "modern", label: "Modern Mint", accent: "#0EA5A0" },
  { key: "bold", label: "Bold Dark", accent: "#0F1E33" },
];

export function MerchantCertTemplates({ token, onMessage, onError }: { token: string | null; onMessage: (m: string) => void; onError: (e: string) => void }) {
  const [templates, setTemplates] = useState<CertTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", style: "classic" as "classic" | "modern" | "bold", accent_color: "#1E3A5F", signatory: "" });
  const [preview, setPreview] = useState<CertTemplate | null>(null);

  async function load() {
    if (!token) return;
    setLoading(true);
    try { setTemplates(await get<CertTemplate[]>("/merchant/certificate-templates", token)); }
    catch (e) { onError(e instanceof Error ? e.message : "Could not load templates"); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [token]);

  async function submit() {
    if (!token || !form.name) { onError("Template name required"); return; }
    try {
      await post("/merchant/certificate-templates", form, token);
      setShowForm(false); setForm({ name: "", style: "classic", accent_color: "#1E3A5F", signatory: "" });
      onMessage("Template created"); await load();
    } catch (e) { onError(e instanceof Error ? e.message : "Could not create template"); }
  }
  async function del(id: string) {
    if (!token) return;
    try { await remove(`/merchant/certificate-templates/${id}`, token); onMessage("Template deleted"); await load(); }
    catch (e) { onError(e instanceof Error ? e.message : "Could not delete"); }
  }

  if (loading) return <ActivityIndicator color={colors.green} />;
  return <>
    <View style={s.result}>
      <Text style={ui.h2}>Certificate templates</Text>
      <Button testID="add-template" label="New template" small onPress={() => setShowForm(!showForm)} />
    </View>
    {showForm && <View style={s.info}>
      <Text style={s.label}>Template name</Text>
      <TextInput testID="tpl-name" style={s.formInput} value={form.name} onChangeText={name => setForm({ ...form, name })} placeholder="e.g. Data Science Certificate" placeholderTextColor={colors.muted} />
      <Text style={s.label}>Style</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {STYLE_OPTIONS.map(so => <Pressable key={so.key} onPress={() => setForm({ ...form, style: so.key, accent_color: so.accent })} style={[s.pill, form.style === so.key && s.activePill]}>
          <Text style={[s.pillText, form.style === so.key && { color: colors.white }]}>{so.label}</Text>
        </Pressable>)}
      </View>
      <Text style={s.label}>Accent color (hex)</Text>
      <TextInput style={s.formInput} value={form.accent_color} onChangeText={accent_color => setForm({ ...form, accent_color })} placeholder="#1E3A5F" placeholderTextColor={colors.muted} autoCapitalize="none" />
      <Text style={s.label}>Signatory name (optional)</Text>
      <TextInput style={s.formInput} value={form.signatory} onChangeText={signatory => setForm({ ...form, signatory })} placeholder="Program Director" placeholderTextColor={colors.muted} />
      <View style={{ flexDirection: "row", gap: 8 }}>
        <Button label="Cancel" secondary small onPress={() => setShowForm(false)} />
        <View style={{ flex: 1 }}><Button testID="tpl-submit" label="Create template" onPress={submit} /></View>
      </View>
    </View>}
    {templates.length ? templates.map(t => <View key={t.id} style={s.info}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
        <View style={[s.rowIcon, { backgroundColor: (t.accent_color || colors.green) + "22" }]}>
          <Icon name="ribbon-outline" size={17} color={t.accent_color || colors.green} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={ui.cardTitle}>{t.name}</Text>
          <Text style={ui.smallMuted}>{t.style} · {t.accent_color}{t.signatory ? ` · ${t.signatory}` : ""}</Text>
        </View>
        <Tag tone="green">{t.status}</Tag>
      </View>
      <View style={{ flexDirection: "row", gap: 8, marginTop: 6 }}>
        <Button label="Preview" small secondary onPress={() => setPreview(t)} />
        <Button testID={`tpl-del-${t.id}`} label="Delete" small secondary onPress={() => del(t.id)} />
      </View>
    </View>) : <EmptyState icon="ribbon-outline" title="No templates yet" body="Create your first certificate template to assign it to courses." />}

    <Modal visible={!!preview} animationType="slide" transparent onRequestClose={() => setPreview(null)}>
      <View style={s.modalWrap}><View style={s.modal}>
        <View style={s.handle} />
        <View style={s.modalHeader}>
          <Text style={ui.h2}>{preview?.name}</Text>
          <Pressable onPress={() => setPreview(null)} style={s.iconButton}><Icon name="close" size={20} /></Pressable>
        </View>
        {preview && <View style={[s.info, { alignItems: "center", padding: 20, backgroundColor: preview.style === "bold" ? "#0F1E33" : colors.white, borderColor: preview.accent_color + "44" }]}>
          <Text style={{ color: preview.accent_color, fontSize: 10, fontWeight: "800", letterSpacing: 3 }}>CORZAAR</Text>
          <Text style={{ color: preview.accent_color, fontSize: 22, fontWeight: "800", marginTop: 12 }}>Certificate of Completion</Text>
          <Text style={{ color: preview.style === "bold" ? "#DFF5EB" : colors.muted, fontSize: 11, marginTop: 8 }}>This is to certify that</Text>
          <Text style={{ color: preview.style === "bold" ? colors.white : colors.ink, fontSize: 20, fontWeight: "800", marginTop: 6 }}>Student Name</Text>
          <Text style={{ color: preview.style === "bold" ? "#DFF5EB" : colors.muted, fontSize: 11, marginTop: 8 }}>has successfully completed</Text>
          <Text style={{ color: preview.accent_color, fontSize: 14, fontWeight: "700", marginTop: 6 }}>Course Title</Text>
          {preview.signatory ? <Text style={{ color: preview.style === "bold" ? "#DFF5EB" : colors.muted, fontSize: 10, marginTop: 10, letterSpacing: 1 }}>AUTHORISED · {preview.signatory.toUpperCase()}</Text> : null}
          <View style={{ marginTop: 16, alignItems: "center" }}>
            <View style={{ width: 60, height: 60, borderRadius: 30, backgroundColor: "#0EA5A0", alignItems: "center", justifyContent: "center" }}>
              <Text style={{ color: colors.white, fontSize: 8, fontWeight: "800" }}>CORZAAR</Text>
              <Text style={{ color: colors.white, fontSize: 8, fontWeight: "800" }}>VERIFIED</Text>
            </View>
          </View>
        </View>}
      </View></View>
    </Modal>
  </>;
}

/** Course certificate config editor (inline within Courses tab). */
export function CourseCertConfigCard({ course, token, templates, onSaved, onError }: { course: Course; token: string | null; templates: CertTemplate[]; onSaved: () => void; onError: (e: string) => void }) {
  const cfg = course.certificate_config || { enabled: false, template_id: null, certificate_name: "Certificate of Completion", completion_percent: 100, issue_method: "automatic" as const };
  const [state, setState] = useState<CertConfig>(cfg);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  async function save() {
    if (!token) return;
    setBusy(true);
    try { await put(`/merchant/courses/${course.id}/certificate`, state, token); onSaved(); }
    catch (e) { onError(e instanceof Error ? e.message : "Could not save"); }
    finally { setBusy(false); }
  }
  return <View style={s.info}>
    <Pressable onPress={() => setExpanded(!expanded)} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
      <Icon name="ribbon-outline" size={18} color={colors.green} />
      <Text style={ui.cardTitle}>Certificate · {course.title}</Text>
      <Icon name={expanded ? "chevron-up" : "chevron-down"} size={18} color={colors.muted} />
    </Pressable>
    {expanded && <>
      <Pressable onPress={() => setState({ ...state, enabled: !state.enabled })} style={{ flexDirection: "row", gap: 8, alignItems: "center", padding: 6 }}>
        <Icon name={state.enabled ? "checkbox" : "square-outline"} size={20} color={state.enabled ? colors.green : colors.muted} />
        <Text style={s.body}>Certificate available for this course</Text>
      </Pressable>
      {state.enabled && <>
        <Text style={s.label}>Template</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 4 }}>
          <Pressable onPress={() => setState({ ...state, template_id: null })} style={[s.pill, !state.template_id && s.activePill, { flexShrink: 0 }]}>
            <Text style={[s.pillText, !state.template_id && { color: colors.white }]}>Default</Text>
          </Pressable>
          {templates.map(t => <Pressable key={t.id} onPress={() => setState({ ...state, template_id: t.id })} style={[s.pill, state.template_id === t.id && s.activePill, { flexShrink: 0 }]}>
            <Text style={[s.pillText, state.template_id === t.id && { color: colors.white }]}>{t.name}</Text>
          </Pressable>)}
        </ScrollView>
        <Text style={s.label}>Certificate name</Text>
        <TextInput style={s.formInput} value={state.certificate_name || ""} onChangeText={certificate_name => setState({ ...state, certificate_name })} placeholder="Certificate of Completion" placeholderTextColor={colors.muted} />
        <Text style={s.label}>Completion required (%)</Text>
        <TextInput style={s.formInput} value={String(state.completion_percent)} onChangeText={v => setState({ ...state, completion_percent: Math.max(10, Math.min(100, Number(v) || 100)) })} keyboardType="numeric" placeholderTextColor={colors.muted} />
        <Text style={s.label}>Issue method</Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          {(["automatic", "manual"] as const).map(m => <Pressable key={m} onPress={() => setState({ ...state, issue_method: m })} style={[s.pill, state.issue_method === m && s.activePill]}>
            <Text style={[s.pillText, state.issue_method === m && { color: colors.white }]}>{m === "automatic" ? "Automatic" : "Manual approval"}</Text>
          </Pressable>)}
        </View>
      </>}
      <Button testID={`cert-save-${course.id}`} label={busy ? "Saving…" : "Save certificate settings"} small onPress={save} />
    </>}
  </View>;
}

export function MerchantCertificatesTab({ token, onMessage, onError }: { token: string | null; onMessage: (m: string) => void; onError: (e: string) => void }) {
  const [data, setData] = useState<{ certificates: Certificate[]; counts: any } | null>(null);
  const [templates, setTemplates] = useState<CertTemplate[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [tab, setTab] = useState<"pending" | "issued" | "revoked" | "templates" | "config">("pending");

  async function load() {
    if (!token) return;
    try {
      const [d, t, c] = await Promise.all([
        get<{ certificates: Certificate[]; counts: any }>("/merchant/certificates", token),
        get<CertTemplate[]>("/merchant/certificate-templates", token),
        get<Course[]>("/merchant/courses", token),
      ]);
      setData(d); setTemplates(t); setCourses(c);
    } catch (e) { onError(e instanceof Error ? e.message : "Could not load"); }
  }
  useEffect(() => { void load(); }, [token]);

  async function approve(id: string) {
    if (!token) return;
    try { await post(`/merchant/certificates/${id}/approve`, {}, token); onMessage("Certificate approved & issued"); await load(); }
    catch (e) { onError(e instanceof Error ? e.message : "Could not approve"); }
  }
  async function reject(id: string) {
    if (!token) return;
    try { await post(`/merchant/certificates/${id}/reject`, {}, token); onMessage("Certificate rejected"); await load(); }
    catch (e) { onError(e instanceof Error ? e.message : "Could not reject"); }
  }

  if (!data) return <ActivityIndicator color={colors.green} />;
  const filtered = tab === "templates" || tab === "config" ? [] : data.certificates.filter(c => c.status === tab.replace("pending", "pending_approval") as any);
  return <>
    <View style={s.metrics}>
      <Pressable style={{ flex: 1 }} onPress={() => setTab("pending")}><View style={[s.metric, tab === "pending" && { borderColor: colors.green }] as any}><View style={s.metricIcon}><Icon name="hourglass-outline" size={17} color={colors.orange} /></View><Text style={ui.metricValue}>{data.counts?.pending_approval || 0}</Text><Text style={ui.metricLabel}>Pending</Text></View></Pressable>
      <Pressable style={{ flex: 1 }} onPress={() => setTab("issued")}><View style={[s.metric, tab === "issued" && { borderColor: colors.green }] as any}><View style={s.metricIcon}><Icon name="ribbon-outline" size={17} color={colors.green} /></View><Text style={ui.metricValue}>{data.counts?.issued || 0}</Text><Text style={ui.metricLabel}>Issued</Text></View></Pressable>
      <Pressable style={{ flex: 1 }} onPress={() => setTab("revoked")}><View style={[s.metric, tab === "revoked" && { borderColor: colors.green }] as any}><View style={s.metricIcon}><Icon name="close-circle-outline" size={17} color={colors.red} /></View><Text style={ui.metricValue}>{data.counts?.revoked || 0}</Text><Text style={ui.metricLabel}>Revoked</Text></View></Pressable>
    </View>
    <View style={{ flexDirection: "row", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
      {(["pending", "issued", "revoked", "templates", "config"] as const).map(t => <Pressable key={t} testID={`certtab-${t}`} onPress={() => setTab(t)} style={[s.pill, tab === t && s.activePill]}>
        <Text style={[s.pillText, tab === t && { color: colors.white }]}>{t === "pending" ? "Approvals" : t === "config" ? "Configure" : t.charAt(0).toUpperCase() + t.slice(1)}</Text>
      </Pressable>)}
    </View>
    {tab === "templates" && <MerchantCertTemplates token={token} onMessage={m => { onMessage(m); void load(); }} onError={onError} />}
    {tab === "config" && <>
      <SectionTitle title="Configure certificate per course" />
      {courses.length ? courses.map(c => <CourseCertConfigCard key={c.id} course={c} token={token} templates={templates} onSaved={() => { onMessage("Settings saved"); void load(); }} onError={onError} />) : <EmptyState icon="library-outline" title="No courses yet" body="Create a course first to configure its certificate." />}
    </>}
    {(tab === "pending" || tab === "issued" || tab === "revoked") && <>
      <SectionTitle title={tab === "pending" ? "Pending approvals" : tab === "issued" ? "Issued certificates" : "Revoked certificates"} />
      {filtered.length ? filtered.map(cert => <View key={cert.id} style={s.info}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
          <View style={s.rowIcon}><Icon name="ribbon-outline" size={17} color={colors.green} /></View>
          <View style={{ flex: 1 }}>
            <Text style={ui.cardTitle}>{cert.student_name || "Learner"} · {cert.course_title}</Text>
            <Text style={ui.smallMuted}>{cert.certificate_id}</Text>
            <Text style={ui.smallMuted}>Completed {String(cert.completion_date || "").slice(0, 10)}</Text>
          </View>
          <Tag tone={cert.status === "issued" ? "green" : cert.status === "revoked" ? "gray" : "orange"}>{cert.status.replace("_", " ")}</Tag>
        </View>
        {cert.status === "pending_approval" && <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
          <Button testID={`cert-reject-${cert.id}`} label="Reject" small secondary onPress={() => reject(cert.id)} />
          <View style={{ flex: 1 }}><Button testID={`cert-approve-${cert.id}`} label="Approve & Issue" small onPress={() => approve(cert.id)} /></View>
        </View>}
      </View>) : <EmptyState icon="ribbon-outline" title={`No ${tab === "pending" ? "pending" : tab} certificates`} body={tab === "pending" ? "Certificates awaiting your approval will appear here." : "Certificates in this state will appear here."} />}
    </>}
  </>;
}

export function AdminCertificatesTab({ token, onMessage, onError }: { token: string | null; onMessage: (m: string) => void; onError: (e: string) => void }) {
  const [data, setData] = useState<{ certificates: Certificate[]; counts: any; templates: CertTemplate[] } | null>(null);
  const [query, setQuery] = useState("");
  async function load() {
    if (!token) return;
    try { setData(await get<any>("/admin/certificates", token)); }
    catch (e) { onError(e instanceof Error ? e.message : "Could not load"); }
  }
  useEffect(() => { void load(); }, [token]);
  async function revoke(id: string) {
    if (!token) return;
    try { await post(`/admin/certificates/${id}/revoke`, {}, token); onMessage("Certificate revoked"); await load(); }
    catch (e) { onError(e instanceof Error ? e.message : "Could not revoke"); }
  }
  if (!data) return <ActivityIndicator color={colors.green} />;
  const filtered = data.certificates.filter(c => !query.trim() || c.certificate_id.toLowerCase().includes(query.toLowerCase()) || (c.student_name || "").toLowerCase().includes(query.toLowerCase()) || (c.course_title || "").toLowerCase().includes(query.toLowerCase()));
  return <>
    <View style={s.metrics}>
      <View style={s.metric}><View style={s.metricIcon}><Icon name="ribbon-outline" size={17} color={colors.green} /></View><Text style={ui.metricValue}>{data.counts?.total || 0}</Text><Text style={ui.metricLabel}>Total certs</Text></View>
      <View style={s.metric}><View style={s.metricIcon}><Icon name="hourglass-outline" size={17} color={colors.orange} /></View><Text style={ui.metricValue}>{data.counts?.pending_approval || 0}</Text><Text style={ui.metricLabel}>Pending</Text></View>
      <View style={s.metric}><View style={s.metricIcon}><Icon name="close-circle-outline" size={17} color={colors.red} /></View><Text style={ui.metricValue}>{data.counts?.revoked || 0}</Text><Text style={ui.metricLabel}>Revoked</Text></View>
    </View>
    <View style={s.searchInput}>
      <Icon name="search" size={20} color={colors.muted} />
      <TextInput testID="admin-cert-search" style={s.input} value={query} onChangeText={setQuery} placeholder="Search by ID, student, or course" placeholderTextColor={colors.muted} autoCapitalize="none" />
    </View>
    <SectionTitle title={`Certificates · ${filtered.length}`} action="Refresh" onAction={load} />
    {filtered.length ? filtered.map(cert => <View key={cert.id} style={s.info}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
        <View style={s.rowIcon}><Icon name="ribbon-outline" size={17} color={colors.green} /></View>
        <View style={{ flex: 1 }}>
          <Text style={ui.cardTitle}>{cert.student_name || "Learner"} · {cert.course_title}</Text>
          <Text style={ui.smallMuted}>{cert.certificate_id}</Text>
          <Text style={ui.smallMuted}>Issued {String(cert.issue_date || cert.completion_date || "").slice(0, 10)}</Text>
        </View>
        <Tag tone={cert.status === "issued" ? "green" : cert.status === "revoked" ? "gray" : "orange"}>{cert.status.replace("_", " ")}</Tag>
      </View>
      {cert.status === "issued" && <View style={{ marginTop: 6 }}><Button testID={`admin-revoke-${cert.id}`} label="Revoke certificate" small secondary onPress={() => revoke(cert.id)} /></View>}
    </View>) : <EmptyState icon="ribbon-outline" title="No certificates found" body="Try clearing the search or wait for students to earn certificates." />}
    <SectionTitle title={`Templates · ${data.templates.length}`} />
    {data.templates.length ? data.templates.map(t => <View key={t.id} style={s.row}>
      <View style={[s.rowIcon, { backgroundColor: (t.accent_color || colors.green) + "22" }]}><Icon name="ribbon-outline" size={17} color={t.accent_color || colors.green} /></View>
      <View style={{ flex: 1 }}><Text style={ui.cardTitle}>{t.name}</Text><Text style={ui.smallMuted}>{t.style} · {t.accent_color}</Text></View>
      <Tag tone="green">{t.status}</Tag>
    </View>) : <EmptyState icon="ribbon-outline" title="No templates yet" body="Merchant certificate templates will appear here for oversight." />}
  </>;
}
