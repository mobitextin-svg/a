import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar, Card, Button, Tag } from '../../src/components/ui';
import { colors, radius } from '../../src/theme';
import { useApp } from '../../src/store';
import { GROUPS, getUser } from '../../src/data';

export default function Group() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const { state, joinGroup, leaveGroup } = useApp();
  const group = GROUPS.find((g) => g.id === id);

  if (!group) return <SafeAreaView style={styles.center}><Text>Group not found</Text></SafeAreaView>;

  const joined = state.joinedGroups.includes(group.id);
  const groupChat = state.chats.find((c) => c.type === 'group' && c.groupId === group.id);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} style={styles.iconCircle}><Ionicons name="chevron-back" size={22} color={colors.ink} /></Pressable>
      </View>

      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 30 }}>
        <View style={{ alignItems: 'center' }}>
          <View style={[styles.bigIcon, { backgroundColor: group.color }]}><Ionicons name="people" size={40} color="#fff" /></View>
          <Text style={styles.name}>{group.name}</Text>
          <Text style={styles.meta}>{group.institution}</Text>
          <Tag label={`${group.members.length} members`} color={colors.accent} />
        </View>

        <View style={{ flexDirection: 'row', marginTop: 20 }}>
          {groupChat && (
            <Button title="Open Group Chat" icon="chatbubbles" onPress={() => router.push(`/chat/${groupChat.id}`)} style={{ flex: 1, marginRight: joined ? 8 : 0 }} />
          )}
          {joined ? (
            <Button title="Leave" variant="ghost" onPress={() => leaveGroup(group.id)} style={{ flex: groupChat ? 0.6 : 1, marginLeft: groupChat ? 8 : 0 }} />
          ) : (
            <Button title="Join Group" icon="add" onPress={() => joinGroup(group.id)} style={{ flex: 1 }} />
          )}
        </View>

        <Text style={styles.section}>Members</Text>
        {group.members.map((mid) => {
          const u = getUser(mid);
          if (!u) return null;
          return (
            <Card key={mid} style={{ marginBottom: 10, flexDirection: 'row', alignItems: 'center' }} onPress={() => router.push(`/user/${mid}`)}>
              <Avatar name={u.name} size={46} />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.cardTitle}>{u.name}</Text>
                <Text style={styles.meta}>{u.headline}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </Card>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  topBar: { paddingHorizontal: 16, paddingTop: 6 },
  iconCircle: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border },
  bigIcon: { width: 84, height: 84, borderRadius: 26, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  name: { fontSize: 22, fontWeight: '900', color: colors.ink, textAlign: 'center' },
  meta: { color: colors.muted, marginTop: 4, marginBottom: 4 },
  section: { fontSize: 18, fontWeight: '800', color: colors.ink, marginTop: 24, marginBottom: 12 },
  cardTitle: { fontWeight: '800', color: colors.ink, fontSize: 15.5 },
});
