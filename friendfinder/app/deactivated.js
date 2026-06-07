import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button } from '../src/components/ui';
import { colors } from '../src/theme';
import { useApp } from '../src/store';

// Shown while the account is deactivated. Data is kept; logging back in
// (Reactivate) restores everything.
export default function Deactivated() {
  const router = useRouter();
  const { reactivate, logout } = useApp();

  const reactivateNow = () => { reactivate(); router.replace('/(tabs)'); };
  const signOut = () => { logout(); router.replace('/(auth)/welcome'); };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={styles.wrap}>
        <View style={styles.iconWrap}>
          <Ionicons name="pause-circle" size={56} color={colors.warning} />
        </View>
        <Text style={styles.title}>Account Deactivated</Text>
        <Text style={styles.body}>
          Your account is temporarily deactivated and hidden from search and other members.
          Your data is safely stored. You can reactivate anytime — just log back in.
        </Text>

        <Button title="Reactivate My Account" icon="play-circle" onPress={reactivateNow} style={{ marginTop: 24, alignSelf: 'stretch' }} />
        <Button title="Log Out" variant="ghost" icon="log-out-outline" onPress={signOut} style={{ marginTop: 12, alignSelf: 'stretch' }} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28 },
  iconWrap: { width: 96, height: 96, borderRadius: 48, backgroundColor: '#fff7ed', alignItems: 'center', justifyContent: 'center', marginBottom: 18 },
  title: { fontSize: 24, fontWeight: '900', color: colors.ink, textAlign: 'center' },
  body: { color: colors.body, fontSize: 15, textAlign: 'center', marginTop: 12, lineHeight: 22 },
});
