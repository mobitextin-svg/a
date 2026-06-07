import React, { useMemo, useState, useEffect } from 'react';
import { View, Text, StyleSheet, TextInput, FlatList, Pressable, ScrollView } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar, Tag, Chip, Empty, Button } from '../../src/components/ui';
import { colors, radius } from '../../src/theme';
import { useApp, matchScore } from '../../src/store';
import { BATCHES, DEPARTMENTS, LEVEL_FILTERS, levelFilterByLabel } from '../../src/data';

// Smart search: free-text across name/institution/course/dept/city/batch,
// plus quick batch & department filters. Tokenised so "ABC College 2015 ECE"
// matches all terms.
export default function Search() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const { allUsers, state, sendRequest } = useApp();
  const [q, setQ] = useState('');
  const [batch, setBatch] = useState(null);
  const [dept, setDept] = useState(null);
  const [level, setLevel] = useState(null); // a LEVEL_FILTERS entry

  // Preset the level filter when arriving from a "Find by level" shortcut.
  useEffect(() => {
    if (params.level) setLevel(levelFilterByLabel(params.level));
  }, [params.level, params.t]);

  const results = useMemo(() => {
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    return allUsers
      .filter((u) => {
        const hay = [
          u.name, u.city, u.state, u.headline,
          ...u.education.flatMap((e) => [e.name, e.course, e.department, e.batch, e.type, e.level]),
        ].join(' ').toLowerCase();
        const textOk = terms.every((t) => hay.includes(t));
        const batchOk = !batch || u.education.some((e) => e.batch === batch);
        const deptOk = !dept || u.education.some((e) => e.department === dept);
        const levelOk = !level || u.education.some((e) => level.match(e));
        return textOk && batchOk && deptOk && levelOk;
      })
      .map((u) => ({
        user: u,
        ...matchScore(state.me, u),
        // Which education record satisfied the active level filter.
        levelMatch: level ? u.education.find((e) => level.match(e)) : null,
      }))
      .sort((a, b) => b.score - a.score);
  }, [q, batch, dept, level, allUsers, state.me]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.head}>
        <Text style={styles.title}>Smart Search</Text>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput
            placeholder='e.g. "ABC College 2015 ECE"'
            placeholderTextColor={colors.muted}
            value={q}
            onChangeText={setQ}
            style={styles.input}
            autoCorrect={false}
          />
          {q ? <Pressable onPress={() => setQ('')}><Ionicons name="close-circle" size={18} color={colors.muted} /></Pressable> : null}
        </View>
      </View>

      {/* Filters */}
      <View style={{ paddingLeft: 20, marginTop: 4 }}>
        <Text style={styles.filterLabel}>Education Level</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingRight: 16 }}>
          <Chip label="Any" active={!level} onPress={() => setLevel(null)} />
          {LEVEL_FILTERS.map((lf) => (
            <Chip key={lf.label} label={lf.label} active={level?.label === lf.label} onPress={() => setLevel(lf)} />
          ))}
        </ScrollView>
        <Text style={styles.filterLabel}>Batch Year</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingRight: 16 }}>
          <Chip label="Any" active={!batch} onPress={() => setBatch(null)} />
          {BATCHES.map((b) => <Chip key={b} label={b} active={batch === b} onPress={() => setBatch(b)} />)}
        </ScrollView>
        <Text style={styles.filterLabel}>Department</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingRight: 16 }}>
          <Chip label="Any" active={!dept} onPress={() => setDept(null)} />
          {DEPARTMENTS.map((d) => <Chip key={d} label={d} active={dept === d} onPress={() => setDept(d)} />)}
        </ScrollView>
      </View>

      <Text style={styles.count}>{results.length} {results.length === 1 ? 'person' : 'people'} found</Text>

      <FlatList
        data={results}
        keyExtractor={(item) => item.user.id}
        contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 24 }}
        ListEmptyComponent={<Empty icon="search-outline" title="No matches" subtitle="Try a different name, college or batch year." />}
        renderItem={({ item }) => {
          const u = item.user;
          const requested = state.outgoing.includes(u.id);
          const friend = state.friends.includes(u.id);
          const ed = u.education[0];
          return (
            <Pressable style={styles.row} onPress={() => router.push(`/user/${u.id}`)}>
              <Avatar name={u.name} size={52} />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Text style={styles.name}>{u.name}</Text>
                  {u.verified ? <Ionicons name="checkmark-circle" size={15} color={colors.primary} style={{ marginLeft: 5 }} /> : null}
                </View>
                <Text style={styles.meta} numberOfLines={1}>{ed?.name} • {ed?.batch}</Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center' }}>
                  {item.levelMatch ? (
                    <Tag
                      label={`${level.label} • ${item.levelMatch.course || item.levelMatch.name || ''}`.replace(/ • $/, '')}
                      color={colors.accent}
                      icon="school"
                    />
                  ) : null}
                  {item.reasons[0] ? <Tag label={item.reasons[0]} color={colors.purple} icon="sparkles" /> : (!item.levelMatch && <Text style={styles.meta}>{u.city}</Text>)}
                </View>
              </View>
              {friend ? (
                <Ionicons name="chatbubble-ellipses" size={22} color={colors.primary} />
              ) : (
                <Button small title={requested ? 'Sent' : 'Add'} variant={requested ? 'ghost' : 'soft'} onPress={() => sendRequest(u.id)} />
              )}
            </Pressable>
          );
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  head: { paddingHorizontal: 20, paddingTop: 8 },
  title: { fontSize: 24, fontWeight: '900', color: colors.ink, marginBottom: 12 },
  searchBar: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, paddingVertical: 13, paddingHorizontal: 16, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.border },
  input: { flex: 1, marginLeft: 10, fontSize: 15.5, color: colors.ink },
  filterLabel: { fontWeight: '700', color: colors.ink, fontSize: 13, marginTop: 12, marginBottom: 8 },
  count: { color: colors.muted, fontWeight: '700', paddingHorizontal: 20, marginTop: 14, marginBottom: 8, fontSize: 13 },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, padding: 14, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, marginBottom: 10 },
  name: { fontWeight: '800', color: colors.ink, fontSize: 15.5 },
  meta: { color: colors.muted, fontSize: 13, marginTop: 2 },
});
