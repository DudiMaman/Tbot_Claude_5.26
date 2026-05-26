import { View, Text, ScrollView, StyleSheet, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';

const charges = [
  { id: '1', desc: 'ועד בית - מאי', amount: 350, status: 'pending', due: '2026-06-01' },
  { id: '2', desc: 'ועד בית - אפריל', amount: 350, status: 'paid', due: '2026-05-01' },
  { id: '3', desc: 'ועד בית - מרץ', amount: 350, status: 'paid', due: '2026-04-01' },
];

export default function ChargesScreen() {
  const router = useRouter();
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.title}>חיובים</Text>
      {charges.map((c) => (
        <View key={c.id} style={styles.row}>
          <View>
            <Text style={styles.desc}>{c.desc}</Text>
            <Text style={styles.due}>פירעון: {c.due}</Text>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={styles.amount}>₪{c.amount}</Text>
            <View style={[styles.badge, c.status === 'paid' ? styles.badgePaid : styles.badgePending]}>
              <Text style={[styles.badgeText, c.status === 'paid' ? styles.badgeTextPaid : styles.badgeTextPending]}>
                {c.status === 'paid' ? 'שולם' : 'ממתין'}
              </Text>
            </View>
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  title: { fontSize: 24, fontWeight: '700', writingDirection: 'rtl', marginBottom: 12 },
  row: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  desc: { fontWeight: '600', writingDirection: 'rtl' },
  due: { color: '#64748b', fontSize: 12, marginTop: 2, writingDirection: 'rtl' },
  amount: { fontWeight: '700', fontSize: 18 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8, marginTop: 4 },
  badgePaid: { backgroundColor: '#dcfce7' },
  badgePending: { backgroundColor: '#fef3c7' },
  badgeText: { fontSize: 11, fontWeight: '600' },
  badgeTextPaid: { color: '#166534' },
  badgeTextPending: { color: '#92400e' },
});
