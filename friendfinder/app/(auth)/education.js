import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button } from '../../src/components/ui';
import EducationForm from '../../src/components/EducationForm';
import EducationCard from '../../src/components/EducationCard';
import { colors } from '../../src/theme';
import { useApp } from '../../src/store';

// Step 2: add one or more education entries (any type), then enter the app.
export default function Education() {
  const router = useRouter();
  const { login } = useApp();
  const params = useLocalSearchParams();

  const [entries, setEntries] = useState([]);

  const addEntry = (entry) => setEntries((e) => [...e, entry]);
  const removeEntry = (i) => setEntries((e) => e.filter((_, idx) => idx !== i));

  const finish = () => {
    const first = entries[0];
    login({
      name: params.name,
      nickname: params.nickname || '',
      gender: params.gender || '',
      dob: params.dob || '',
      mobile: params.mobile || '',
      email: params.email || '',
      mobileHidden: params.mobileHidden === '1',
      emailHidden: params.emailHidden === '1',
      city: params.city,
      state: params.state,
      headline: first ? [first.course, first.department, first.batch].filter(Boolean).join(' • ') || 'BatchMate member' : 'BatchMate member',
      verified: false,
      education: entries,
    });
    router.replace('/(tabs)');
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={styles.wrap} keyboardShouldPersistTaps="handled">
        <Text style={styles.step}>STEP 2 OF 2</Text>
        <Text style={styles.title}>Your education history</Text>
        <Text style={styles.sub}>Add your school, diploma, college, university, professional or coaching records to find batchmates.</Text>

        <EducationForm onAdd={addEntry} />

        {entries.length > 0 && (
          <View style={{ marginTop: 18 }}>
            {entries.map((e, i) => (
              <EducationCard key={i} entry={e} onRemove={() => removeEntry(i)} />
            ))}
          </View>
        )}

        <Button title="Finish & Explore" icon="rocket" onPress={finish} style={{ marginTop: 20 }} />
        <Text style={styles.skip} onPress={finish}>Skip for now</Text>
        <View style={{ height: 30 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: 24 },
  step: { color: colors.primary, fontWeight: '800', fontSize: 12, letterSpacing: 1 },
  title: { fontSize: 28, fontWeight: '900', color: colors.ink, marginTop: 6 },
  sub: { color: colors.body, fontSize: 15, marginTop: 6, marginBottom: 20, lineHeight: 22 },
  meta: { color: colors.muted, fontSize: 13, marginTop: 2 },
  skip: { textAlign: 'center', color: colors.muted, fontWeight: '700', marginTop: 14 },
});
