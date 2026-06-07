import React from 'react';
import { View, Text, StyleSheet, FlatList, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar, Empty } from '../../src/components/ui';
import { colors, radius, colorFor, initials } from '../../src/theme';
import { useApp } from '../../src/store';
import { getUser, GROUPS } from '../../src/data';

function timeAgo(ts) {
  const m = Math.floor((Date.now() - ts) / 60000);
  if (m < 1) return 'now';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

export default function Chats() {
  const router = useRouter();
  const { state } = useApp();

  const list = state.chats
    .map((c) => {
      const last = c.messages[c.messages.length - 1];
      const isGroup = c.type === 'group';
      const group = isGroup ? GROUPS.find((g) => g.id === c.groupId) : null;
      const peer = !isGroup ? getUser(c.with) : null;
      return {
        id: c.id,
        title: isGroup ? group?.name : peer?.name,
        color: isGroup ? group?.color : colorFor(peer?.name || ''),
        isGroup,
        last,
      };
    })
    .filter((c) => c.title)
    .sort((a, b) => (b.last?.at || 0) - (a.last?.at || 0));

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.head}>
        <Text style={styles.title}>Chats</Text>
        <Pressable onPress={() => router.push('/(tabs)/search')} style={styles.newBtn}>
          <Ionicons name="create-outline" size={22} color={colors.primary} />
        </Pressable>
      </View>

      <FlatList
        data={list}
        keyExtractor={(c) => c.id}
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 20 }}
        ListEmptyComponent={<Empty icon="chatbubbles-outline" title="No conversations yet" subtitle="Connect with a classmate to start chatting." />}
        renderItem={({ item }) => (
          <Pressable style={styles.row} onPress={() => router.push(`/chat/${item.id}`)}>
            {item.isGroup ? (
              <View style={[styles.groupAv, { backgroundColor: item.color }]}><Ionicons name="people" size={22} color="#fff" /></View>
            ) : (
              <Avatar name={item.title} size={52} />
            )}
            <View style={{ flex: 1, marginLeft: 12 }}>
              <View style={styles.rowTop}>
                <Text style={styles.name} numberOfLines={1}>{item.title}</Text>
                <Text style={styles.time}>{item.last ? timeAgo(item.last.at) : ''}</Text>
              </View>
              <Text style={styles.preview} numberOfLines={1}>
                {item.last ? (item.last.from === 'me' ? 'You: ' : '') + item.last.text : 'No messages yet'}
              </Text>
            </View>
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 8, paddingBottom: 8 },
  title: { fontSize: 24, fontWeight: '900', color: colors.ink },
  newBtn: { width: 42, height: 42, borderRadius: 12, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' },
  row: { flexDirection: 'row', alignItems: 'center', padding: 12, borderRadius: radius.md },
  groupAv: { width: 52, height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center' },
  rowTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  name: { fontWeight: '800', color: colors.ink, fontSize: 16, flex: 1 },
  time: { color: colors.muted, fontSize: 12, marginLeft: 8 },
  preview: { color: colors.muted, fontSize: 14, marginTop: 3 },
});
