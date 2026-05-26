import { View, Text, ScrollView, StyleSheet, TouchableOpacity, Switch } from 'react-native';
import { useState } from 'react';
import { Ionicons } from '@expo/vector-icons';

export default function ProfileScreen() {
  const [whatsapp, setWhatsapp] = useState(true);
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.title}>פרופיל</Text>
      <View style={styles.card}>
        <Text style={styles.name}>דייר 1</Text>
        <Text style={styles.meta}>בעלים — בניין הרצל 10, דירה 1</Text>
      </View>

      <Text style={styles.section}>העדפות התראות</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>WhatsApp</Text>
          <Switch value={whatsapp} onValueChange={setWhatsapp} />
        </View>
      </View>

      <Text style={styles.section}>אמצעי תשלום</Text>
      <TouchableOpacity style={styles.card}>
        <View style={styles.row}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Ionicons name="card" size={20} color="#4f46e5" />
            <Text>Visa ****4242</Text>
          </View>
          <Text style={{ color: '#4f46e5' }}>ערוך</Text>
        </View>
      </TouchableOpacity>

      <TouchableOpacity style={[styles.card, { marginTop: 20 }]}>
        <Text style={{ color: '#ef4444', textAlign: 'center', writingDirection: 'rtl' }}>התנתקות</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  title: { fontSize: 24, fontWeight: '700', writingDirection: 'rtl', marginBottom: 12 },
  card: { backgroundColor: 'white', borderRadius: 12, padding: 16, borderWidth: 1, borderColor: '#e2e8f0', marginBottom: 8 },
  name: { fontSize: 18, fontWeight: '700', writingDirection: 'rtl' },
  meta: { color: '#64748b', marginTop: 2, writingDirection: 'rtl' },
  section: { fontSize: 14, color: '#475569', marginTop: 16, marginBottom: 8, writingDirection: 'rtl' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  rowLabel: { writingDirection: 'rtl' },
});
