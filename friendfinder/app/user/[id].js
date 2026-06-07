import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Alert, Platform } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar, Card, Tag, Button } from '../../src/components/ui';
import { colors, radius } from '../../src/theme';
import { useApp, matchScore } from '../../src/store';
import { getUser } from '../../src/data';

export default function UserProfile() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const { state, sendRequest, cancelRequest, removeFriend, block, startDM } = useApp();
  const u = getUser(id);

  if (!u) {
    return (
      <SafeAreaView style={styles.center}><Text>User not found.</Text></SafeAreaView>
    );
  }

  const isFriend = state.friends.includes(u.id);
  const requested = state.outgoing.includes(u.id);
  const { reasons } = matchScore(state.me, u);

  const confirmBlock = () => {
    const doBlock = () => { block(u.id); router.back(); };
    if (Platform.OS === 'web') doBlock();
    else Alert.alert('Block user', `Block ${u.name}?`, [{ text: 'Cancel', style: 'cancel' }, { text: 'Block', style: 'destructive', onPress: doBlock }]);
  };

  const message = () => { const c = startDM(u.id); router.push(`/chat/${c}`); };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} style={styles.iconCircle}><Ionicons name="chevron-back" size={22} color={colors.ink} /></Pressable>
        <Pressable onPress={confirmBlock} style={styles.iconCircle}><Ionicons name="ban-outline" size={20} color={colors.danger} /></Pressable>
      </View>

      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 30 }} showsVerticalScrollIndicator={false}>
        <View style={{ alignItems: 'center' }}>
          <Avatar name={u.name} size={100} />
          <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 12 }}>
            <Text style={styles.name}>{u.name}</Text>
            {u.verified ? <Ionicons name="checkmark-circle" size={18} color={colors.primary} style={{ marginLeft: 6 }} /> : null}
          </View>
          <Text style={styles.headline}>{u.headline}</Text>
          <Text style={styles.loc}><Ionicons name="location" size={13} color={colors.muted} /> {u.city}, {u.state}</Text>
          {reasons.length > 0 && (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', marginTop: 4 }}>
              {reasons.map((r) => <Tag key={r} label={r} color={colors.purple} icon="sparkles" />)}
            </View>
          )}
        </View>

        {/* Actions */}
        <View style={styles.actions}>
          {isFriend ? (
            <>
              <Button title="Message" icon="chatbubble-ellipses" onPress={message} style={{ flex: 1, marginRight: 8 }} />
              <Button title="Friends" variant="ghost" icon="checkmark-circle" onPress={() => removeFriend(u.id)} style={{ flex: 1, marginLeft: 8 }} />
            </>
          ) : requested ? (
            <Button title="Request Sent — Cancel" variant="ghost" icon="time" onPress={() => cancelRequest(u.id)} style={{ flex: 1 }} />
          ) : (
            <>
              <Button title="Add Friend" icon="person-add" onPress={() => sendRequest(u.id)} style={{ flex: 1, marginRight: 8 }} />
              <Button title="Message" variant="ghost" icon="chatbubble-ellipses" onPress={message} style={{ flex: 1, marginLeft: 8 }} />
            </>
          )}
        </View>

        {/* Work */}
        {u.work && (
          <Card style={{ marginTop: 18, flexDirection: 'row', alignItems: 'center' }}>
            <View style={styles.icon}><Ionicons name="briefcase" size={20} color={colors.primary} /></View>
            <View style={{ marginLeft: 12 }}>
              <Text style={styles.cardTitle}>{u.work.title}</Text>
              <Text style={styles.meta}>{u.work.company}</Text>
            </View>
          </Card>
        )}

        {/* Education */}
        <Text style={styles.section}>Education</Text>
        {u.education.map((e, i) => (
          <Card key={i} style={{ marginBottom: 10, flexDirection: 'row', alignItems: 'center' }}>
            <View style={styles.icon}><Ionicons name="school" size={20} color={colors.primary} /></View>
            <View style={{ flex: 1, marginLeft: 12 }}>
              <Text style={styles.cardTitle}>{e.name}</Text>
              <Text style={styles.meta}>{[e.course, e.department, e.batch].filter(Boolean).join(' • ')}</Text>
            </View>
            <Tag label={e.level} />
          </Card>
        ))}

        {/* Where are they now */}
        {u.where && (
          <Card style={{ marginTop: 8 }}>
            <Text style={styles.cardTitle}>Where are they now?</Text>
            <Text style={[styles.meta, { fontStyle: 'italic', marginTop: 6, lineHeight: 20 }]}>“{u.where}”</Text>
          </Card>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 16, paddingTop: 6 },
  iconCircle: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border },
  name: { fontSize: 24, fontWeight: '900', color: colors.ink },
  headline: { color: colors.body, marginTop: 4, fontWeight: '600' },
  loc: { color: colors.muted, marginTop: 4, fontSize: 13 },
  actions: { flexDirection: 'row', marginTop: 20 },
  icon: { width: 42, height: 42, borderRadius: 12, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  section: { fontSize: 18, fontWeight: '800', color: colors.ink, marginTop: 22, marginBottom: 12 },
  cardTitle: { fontWeight: '800', color: colors.ink, fontSize: 15.5 },
  meta: { color: colors.muted, fontSize: 13, marginTop: 2 },
});
