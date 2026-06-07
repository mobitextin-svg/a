import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, Field, Select } from '../../src/components/ui';
import { colors, radius } from '../../src/theme';
import { DELETE_REASONS } from '../../src/data';
import { useApp } from '../../src/store';

// Delete Account — mock. Password + reason + explicit confirmation.
export default function DeleteAccount() {
  const router = useRouter();
  const { logout } = useApp();
  const [password, setPassword] = useState('');
  const [reason, setReason] = useState('');
  const [agree, setAgree] = useState(false);

  const valid = password.length > 0 && agree;

  const confirmDelete = () => {
    if (!valid) return;
    Alert.alert(
      'Delete Account',
      'Your account and associated data will be permanently deleted. This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete Permanently', style: 'destructive', onPress: logout },
      ]
    );
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={8}><Ionicons name="chevron-back" size={26} color={colors.ink} /></Pressable>
        <Text style={styles.headerTitle}>Delete Account</Text>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={styles.wrap} keyboardShouldPersistTaps="handled">
        <View style={styles.warn}>
          <Ionicons name="warning" size={20} color={colors.danger} />
          <Text style={styles.warnText}>
            This permanently removes your profile, education details, connections and messages.
            This action cannot be undone after the grace period.
          </Text>
        </View>

        <Field label="Enter your password" icon="lock-closed-outline" secureTextEntry value={password} onChangeText={setPassword} />
        <Select label="Reason for deleting (optional)" icon="chatbox-ellipses-outline" placeholder="Select a reason" value={reason} options={DELETE_REASONS} onChange={setReason} />

        <Pressable style={styles.agreeRow} onPress={() => setAgree((a) => !a)}>
          <Ionicons name={agree ? 'checkbox' : 'square-outline'} size={22} color={agree ? colors.danger : colors.muted} />
          <Text style={styles.agreeText}>I understand this action is permanent and cannot be undone.</Text>
        </Pressable>

        <Button title="Delete My Account" variant="danger" icon="trash-outline" onPress={confirmDelete} disabled={!valid} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 18, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card },
  headerTitle: { fontWeight: '900', fontSize: 17, color: colors.ink },
  wrap: { padding: 20 },
  warn: { flexDirection: 'row', backgroundColor: '#fef2f2', borderWidth: 1, borderColor: '#fecaca', borderRadius: radius.sm, padding: 14, marginBottom: 18 },
  warnText: { flex: 1, marginLeft: 10, color: colors.danger, fontSize: 13.5, lineHeight: 19, fontWeight: '600' },
  agreeRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 18 },
  agreeText: { flex: 1, marginLeft: 10, color: colors.ink, fontSize: 14, lineHeight: 19, fontWeight: '600' },
});
