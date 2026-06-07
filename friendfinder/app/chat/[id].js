import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, TextInput, Pressable, FlatList, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Avatar } from '../../src/components/ui';
import { colors, radius, colorFor } from '../../src/theme';
import { useApp } from '../../src/store';
import { getUser, GROUPS } from '../../src/data';

export default function Chat() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const { state, sendMessage } = useApp();
  const [text, setText] = useState('');
  const listRef = useRef(null);

  const chat = state.chats.find((c) => c.id === id);
  const isGroup = chat?.type === 'group';
  const group = isGroup ? GROUPS.find((g) => g.id === chat.groupId) : null;
  const peer = !isGroup && chat ? getUser(chat.with) : null;
  const title = isGroup ? group?.name : peer?.name;

  useEffect(() => {
    const t = setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 200);
    return () => clearTimeout(t);
  }, [chat?.messages.length]);

  if (!chat) return <SafeAreaView style={styles.center}><Text>Chat not found</Text></SafeAreaView>;

  const send = () => {
    if (!text.trim()) return;
    sendMessage(chat.id, text.trim());
    setText('');
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={{ padding: 4 }}><Ionicons name="chevron-back" size={26} color={colors.ink} /></Pressable>
        {isGroup ? (
          <View style={[styles.groupAv, { backgroundColor: group?.color }]}><Ionicons name="people" size={18} color="#fff" /></View>
        ) : (
          <Avatar name={title} size={40} />
        )}
        <View style={{ flex: 1, marginLeft: 10 }}>
          <Text style={styles.title} numberOfLines={1}>{title}</Text>
          <Text style={styles.sub}>{isGroup ? `${group?.members.length} members` : 'Online'}</Text>
        </View>
        <Pressable style={{ padding: 6 }}><Ionicons name="call-outline" size={22} color={colors.primary} /></Pressable>
        <Pressable style={{ padding: 6 }}><Ionicons name="videocam-outline" size={22} color={colors.primary} /></Pressable>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={8}>
        <FlatList
          ref={listRef}
          data={chat.messages}
          keyExtractor={(m) => m.id}
          contentContainerStyle={{ padding: 16, paddingBottom: 8 }}
          renderItem={({ item }) => {
            const mine = item.from === 'me';
            const sender = !mine && isGroup ? getUser(item.from) : null;
            return (
              <View style={[styles.bubbleRow, mine ? styles.right : styles.left]}>
                {!mine && isGroup && <Avatar name={sender?.name} size={28} />}
                <View style={[styles.bubble, mine ? styles.bubbleMine : styles.bubbleOther, !mine && isGroup && { marginLeft: 8 }]}>
                  {!mine && isGroup && <Text style={[styles.sender, { color: colorFor(sender?.name || '') }]}>{sender?.name}</Text>}
                  <Text style={[styles.msgText, mine && { color: '#fff' }]}>{item.text}</Text>
                </View>
              </View>
            );
          }}
        />

        {/* Composer */}
        <View style={styles.composer}>
          <Pressable style={styles.composerIcon}><Ionicons name="add-circle" size={26} color={colors.primary} /></Pressable>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="Message…"
            placeholderTextColor={colors.muted}
            style={styles.composerInput}
            multiline
          />
          {text.trim() ? (
            <Pressable onPress={send} style={styles.sendBtn}><Ionicons name="send" size={18} color="#fff" /></Pressable>
          ) : (
            <Pressable style={styles.sendBtn}><Ionicons name="mic" size={20} color="#fff" /></Pressable>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 8, backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.border },
  groupAv: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  title: { fontWeight: '800', color: colors.ink, fontSize: 16 },
  sub: { color: colors.success, fontSize: 12, marginTop: 1 },
  bubbleRow: { flexDirection: 'row', marginBottom: 10, maxWidth: '82%' },
  left: { alignSelf: 'flex-start' },
  right: { alignSelf: 'flex-end' },
  bubble: { paddingVertical: 9, paddingHorizontal: 13, borderRadius: 18 },
  bubbleMine: { backgroundColor: colors.primary, borderBottomRightRadius: 4 },
  bubbleOther: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderBottomLeftRadius: 4 },
  sender: { fontWeight: '800', fontSize: 12, marginBottom: 2 },
  msgText: { color: colors.ink, fontSize: 15, lineHeight: 20 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', padding: 10, backgroundColor: colors.card, borderTopWidth: 1, borderTopColor: colors.border },
  composerIcon: { paddingBottom: 6, paddingRight: 4 },
  composerInput: { flex: 1, maxHeight: 110, backgroundColor: colors.bg, borderRadius: 20, paddingHorizontal: 14, paddingTop: 10, paddingBottom: 10, fontSize: 15, color: colors.ink, marginHorizontal: 8 },
  sendBtn: { width: 42, height: 42, borderRadius: 21, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
});
