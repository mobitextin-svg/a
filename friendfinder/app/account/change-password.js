import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, Field, Toggle } from '../../src/components/ui';
import { colors, radius } from '../../src/theme';
import { useApp } from '../../src/store';

// Change Password — mock (no backend). Enforces basic strength rules.
export default function ChangePassword() {
  const router = useRouter();
  const { logout } = useApp();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [logoutAll, setLogoutAll] = useState(false);

  const rules = [
    { label: 'At least 8 characters', ok: next.length >= 8 },
    { label: 'Includes a letter and a number', ok: /[a-zA-Z]/.test(next) && /\d/.test(next) },
    { label: 'New & confirm passwords match', ok: !!next && next === confirm },
  ];
  const valid = current.length > 0 && rules.every((r) => r.ok);

  const submit = () => {
    if (!valid) return;
    Alert.alert('Password updated', 'Your password has been changed (demo).', [
      { text: 'OK', onPress: () => (logoutAll ? logout() : router.back()) },
    ]);
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={8}><Ionicons name="chevron-back" size={26} color={colors.ink} /></Pressable>
        <Text style={styles.headerTitle}>Change Password</Text>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={styles.wrap} keyboardShouldPersistTaps="handled">
        <Text style={styles.intro}>Update your account password for better security.</Text>

        <Field label="Current Password" icon="lock-closed-outline" secureTextEntry value={current} onChangeText={setCurrent} />
        <Field label="New Password" icon="key-outline" secureTextEntry value={next} onChangeText={setNext} />
        <Field label="Confirm New Password" icon="key-outline" secureTextEntry value={confirm} onChangeText={setConfirm} />

        <View style={styles.rules}>
          {rules.map((r) => (
            <View key={r.label} style={styles.ruleRow}>
              <Ionicons name={r.ok ? 'checkmark-circle' : 'ellipse-outline'} size={16} color={r.ok ? colors.success : colors.muted} />
              <Text style={[styles.ruleText, r.ok && { color: colors.ink }]}>{r.label}</Text>
            </View>
          ))}
        </View>

        <Toggle label="Log out from all other devices" icon="log-out-outline" value={logoutAll} onValueChange={setLogoutAll} />

        <Button title="Update Password" icon="checkmark-circle" onPress={submit} disabled={!valid} style={{ marginTop: 8 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 18, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card },
  headerTitle: { fontWeight: '900', fontSize: 17, color: colors.ink },
  wrap: { padding: 20 },
  intro: { color: colors.body, fontSize: 14.5, marginBottom: 18, lineHeight: 20 },
  rules: { backgroundColor: colors.card, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.border, padding: 14, marginBottom: 16 },
  ruleRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 5 },
  ruleText: { marginLeft: 8, color: colors.muted, fontSize: 13.5, fontWeight: '600' },
});
