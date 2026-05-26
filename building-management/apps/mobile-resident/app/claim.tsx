import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';

export default function ClaimScreen() {
  const router = useRouter();
  const { b, s } = useLocalSearchParams<{ b?: string; s?: string }>();
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [unit, setUnit] = useState('');
  const [role, setRole] = useState<'owner' | 'renter' | 'family_member'>('owner');
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    try {
      // POST /v1/people/claim with { phone, full_name, building_id: b, unit_number: unit, role }
      await new Promise((r) => setTimeout(r, 600));
      Alert.alert('הבקשה התקבלה', 'נציג חברת הניהול יאשר בקרוב.');
      router.replace('/(tabs)/home');
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>הצטרפו לבניין</Text>
      <Text style={styles.subtitle}>מלאו את הפרטים כדי להתחיל</Text>

      <Text style={styles.label}>שם מלא</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="ישראל ישראלי" />

      <Text style={styles.label}>טלפון (לאימות SMS)</Text>
      <TextInput style={styles.input} value={phone} onChangeText={setPhone} placeholder="050-1234567" keyboardType="phone-pad" />

      <Text style={styles.label}>מספר דירה</Text>
      <TextInput style={styles.input} value={unit} onChangeText={setUnit} placeholder="לדוגמה: 4ב" />

      <Text style={styles.label}>תפקיד</Text>
      <View style={styles.roleRow}>
        {[
          { v: 'owner', l: 'בעלים' },
          { v: 'renter', l: 'שוכר' },
          { v: 'family_member', l: 'בן משפחה' },
        ].map((r) => (
          <TouchableOpacity
            key={r.v}
            style={[styles.roleChip, role === r.v && styles.roleChipActive]}
            onPress={() => setRole(r.v as any)}
          >
            <Text style={[styles.roleChipText, role === r.v && styles.roleChipTextActive]}>{r.l}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={styles.submit} onPress={submit} disabled={loading}>
        <Text style={styles.submitText}>{loading ? 'שולח...' : 'שליחת בקשה'}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'white', padding: 24 },
  title: { fontSize: 28, fontWeight: '700', writingDirection: 'rtl', marginTop: 40 },
  subtitle: { color: '#64748b', marginTop: 4, writingDirection: 'rtl', marginBottom: 24 },
  label: { fontSize: 14, color: '#475569', marginTop: 16, writingDirection: 'rtl' },
  input: {
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 10,
    padding: 12,
    marginTop: 6,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  roleRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  roleChip: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    alignItems: 'center',
  },
  roleChipActive: { borderColor: '#4f46e5', backgroundColor: '#eef2ff' },
  roleChipText: { color: '#475569', writingDirection: 'rtl' },
  roleChipTextActive: { color: '#4f46e5', fontWeight: '600' },
  submit: {
    marginTop: 32,
    backgroundColor: '#4f46e5',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  submitText: { color: 'white', fontSize: 16, fontWeight: '700', writingDirection: 'rtl' },
});
