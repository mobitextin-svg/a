import React, { useMemo } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, FlatList } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar, Card, Tag, Button, SectionTitle, Empty, Chip } from '../../src/components/ui';
import { colors, radius, shadow } from '../../src/theme';
import { useApp } from '../../src/store';
import { getUser, LEVEL_FILTERS } from '../../src/data';

export default function Home() {
  const router = useRouter();
  const { state, suggestions, sendRequest, acceptRequest, rejectRequest, joined, allUsers } = useApp();
  const me = state.me;
  const whereAreThey = suggestions.filter((s) => s.user.where).slice(0, 5);

  // How many people match each education level (for the Home chips).
  const levelCounts = useMemo(() => {
    const map = {};
    LEVEL_FILTERS.forEach((lf) => {
      map[lf.label] = allUsers.filter((u) => (u.education || []).some((e) => lf.match(e))).length;
    });
    return map;
  }, [allUsers]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 28 }}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.hi}>Hi, {me?.name?.split(' ')[0]} 👋</Text>
            <Text style={styles.subHi}>Let's find your old classmates</Text>
          </View>
          <Pressable onPress={() => router.push('/premium')} style={styles.premiumPill}>
            <Ionicons name="star" size={14} color="#fff" />
            <Text style={styles.premiumText}>{state.premium ? 'Premium' : 'Go Premium'}</Text>
          </Pressable>
        </View>

        {/* Search shortcut */}
        <Pressable style={styles.searchBar} onPress={() => router.push('/(tabs)/search')}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <Text style={styles.searchText}>Search college, batch, name…</Text>
        </Pressable>

        {/* Find batchmates by education level */}
        <View style={{ marginTop: 18 }}>
          <Text style={styles.findLabel}>Find batchmates by level</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 20 }}>
            {LEVEL_FILTERS.filter((lf) => levelCounts[lf.label] > 0).map((lf) => (
              <Chip
                key={lf.label}
                label={`${lf.label} · ${levelCounts[lf.label]}`}
                onPress={() => router.push({ pathname: '/(tabs)/search', params: { level: lf.label, t: String(Date.now()) } })}
              />
            ))}
          </ScrollView>
        </View>

        {/* Incoming friend requests */}
        {state.incoming.length > 0 && (
          <View style={styles.section}>
            <SectionTitle>Friend Requests</SectionTitle>
            {state.incoming.map((id) => {
              const u = getUser(id);
              if (!u) return null;
              return (
                <Card key={id} style={styles.reqCard}>
                  <Avatar name={u.name} size={48} />
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={styles.name}>{u.name}</Text>
                    <Text style={styles.meta}>{u.headline}</Text>
                  </View>
                  <Pressable onPress={() => acceptRequest(id)} style={[styles.iconBtn, { backgroundColor: colors.success }]}><Ionicons name="checkmark" size={20} color="#fff" /></Pressable>
                  <Pressable onPress={() => rejectRequest(id)} style={[styles.iconBtn, { backgroundColor: '#fee2e2', marginLeft: 8 }]}><Ionicons name="close" size={20} color={colors.danger} /></Pressable>
                </Card>
              );
            })}
          </View>
        )}

        {/* AI: People You May Know */}
        <View style={styles.section}>
          <View style={styles.aiRow}>
            <SectionTitle action="See all" onAction={() => router.push('/(tabs)/search')}>People You May Know</SectionTitle>
          </View>
          <View style={styles.aiBadge}>
            <Ionicons name="sparkles" size={13} color={colors.purple} />
            <Text style={styles.aiText}>AI matched from your batch & college</Text>
          </View>
          {suggestions.length === 0 ? (
            <Empty title="No suggestions yet" subtitle="Add more education details to find batchmates." />
          ) : (
            <FlatList
              data={suggestions.slice(0, 10)}
              horizontal
              showsHorizontalScrollIndicator={false}
              keyExtractor={(item) => item.user.id}
              contentContainerStyle={{ paddingRight: 16 }}
              renderItem={({ item }) => {
                const requested = state.outgoing.includes(item.user.id);
                return (
                  <Pressable style={[styles.pymk, shadow.card]} onPress={() => router.push(`/user/${item.user.id}`)}>
                    <Avatar name={item.user.name} size={64} />
                    <Text style={styles.pymkName} numberOfLines={1}>{item.user.name}</Text>
                    <Text style={styles.pymkReason} numberOfLines={2}>{item.reasons[0] || item.user.headline}</Text>
                    <Button
                      small
                      title={requested ? 'Requested' : 'Add'}
                      icon={requested ? 'checkmark' : 'person-add'}
                      variant={requested ? 'ghost' : 'primary'}
                      onPress={() => sendRequest(item.user.id)}
                      style={{ marginTop: 10, width: '100%' }}
                    />
                  </Pressable>
                );
              }}
            />
          )}
        </View>

        {/* My batch groups */}
        <View style={styles.section}>
          <SectionTitle action="All groups" onAction={() => router.push('/(tabs)/alumni')}>Your Batch Groups</SectionTitle>
          {joined.map((g) => (
            <Card key={g.id} style={styles.groupCard} onPress={() => router.push(`/group/${g.id}`)}>
              <View style={[styles.groupIcon, { backgroundColor: g.color }]}><Ionicons name="people" size={22} color="#fff" /></View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.name}>{g.name}</Text>
                <Text style={styles.meta}>{g.institution} • {g.members.length} members</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={colors.muted} />
            </Card>
          ))}
        </View>

        {/* Where Are They Now? */}
        <View style={styles.section}>
          <SectionTitle>Where Are They Now?</SectionTitle>
          {whereAreThey.map(({ user }) => (
            <Card key={user.id} style={{ marginBottom: 10 }} onPress={() => router.push(`/user/${user.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Avatar name={user.name} size={44} />
                <View style={{ marginLeft: 12, flex: 1 }}>
                  <Text style={styles.name}>{user.name}</Text>
                  <Text style={styles.meta}>{user.city}</Text>
                </View>
              </View>
              <Text style={styles.update}>“{user.where}”</Text>
            </Card>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 8, paddingBottom: 4 },
  hi: { fontSize: 24, fontWeight: '900', color: colors.ink },
  subHi: { color: colors.muted, marginTop: 2 },
  premiumPill: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.gold, paddingVertical: 8, paddingHorizontal: 12, borderRadius: radius.pill },
  premiumText: { color: '#fff', fontWeight: '800', fontSize: 12.5, marginLeft: 5 },
  searchBar: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, marginHorizontal: 20, marginTop: 14, paddingVertical: 14, paddingHorizontal: 16, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border },
  searchText: { color: colors.muted, marginLeft: 10, fontSize: 15 },
  findLabel: { fontWeight: '800', color: colors.ink, fontSize: 14, paddingHorizontal: 20, marginBottom: 10 },
  section: { paddingHorizontal: 20, marginTop: 22 },
  aiRow: { },
  aiBadge: { flexDirection: 'row', alignItems: 'center', marginTop: -6, marginBottom: 12 },
  aiText: { color: colors.purple, fontWeight: '700', fontSize: 12.5, marginLeft: 5 },
  reqCard: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  name: { fontWeight: '800', color: colors.ink, fontSize: 15 },
  meta: { color: colors.muted, fontSize: 13, marginTop: 2 },
  iconBtn: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  pymk: { width: 160, backgroundColor: colors.card, borderRadius: radius.md, padding: 16, marginRight: 12, alignItems: 'center', borderWidth: 1, borderColor: colors.border },
  pymkName: { fontWeight: '800', color: colors.ink, marginTop: 10, fontSize: 14.5 },
  pymkReason: { color: colors.muted, fontSize: 12, textAlign: 'center', marginTop: 4, height: 32 },
  groupCard: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  groupIcon: { width: 44, height: 44, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  update: { color: colors.body, fontStyle: 'italic', marginTop: 10, lineHeight: 20 },
});
