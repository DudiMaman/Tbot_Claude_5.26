import { View, Text, ScrollView, StyleSheet, TouchableOpacity, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const tasks = [
  { id: '1', time: '09:00', title: 'נזילה - דירה 12', building: 'הרצל 10', priority: 'high', status: 'todo' },
  { id: '2', time: '11:30', title: 'תאורת מסדרון', building: 'הרצל 10', priority: 'med', status: 'todo' },
  { id: '3', time: '14:00', title: 'הידית של דלת חדר אשפה', building: 'מגדל בן יהודה', priority: 'low', status: 'todo' },
];

export default function TodayScreen() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16, paddingTop: 60 }}>
      <Text style={styles.title}>היום</Text>
      <Text style={styles.subtitle}>{tasks.length} משימות מתוכננות</Text>

      {tasks.map((t) => (
        <View key={t.id} style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.time}>{t.time}</Text>
            <View style={[styles.badge, t.priority === 'high' ? styles.badgeHigh : t.priority === 'med' ? styles.badgeMed : styles.badgeLow]}>
              <Text style={styles.badgeText}>
                {t.priority === 'high' ? 'דחוף' : t.priority === 'med' ? 'בינוני' : 'נמוך'}
              </Text>
            </View>
          </View>
          <Text style={styles.taskTitle}>{t.title}</Text>
          <Text style={styles.building}>{t.building}</Text>

          <View style={styles.actions}>
            <TouchableOpacity style={styles.action} onPress={() => Linking.openURL('https://waze.com/ul?q=' + encodeURIComponent(t.building))}>
              <Ionicons name="navigate" size={18} color="#4f46e5" />
              <Text style={styles.actionText}>נווט</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.action}>
              <Ionicons name="camera" size={18} color="#4f46e5" />
              <Text style={styles.actionText}>צלם</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.action, styles.actionPrimary]}>
              <Ionicons name="checkmark" size={18} color="white" />
              <Text style={[styles.actionText, { color: 'white' }]}>סיים</Text>
            </TouchableOpacity>
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  title: { fontSize: 28, fontWeight: '700', writingDirection: 'rtl' },
  subtitle: { color: '#64748b', marginTop: 4, marginBottom: 16, writingDirection: 'rtl' },
  card: { backgroundColor: 'white', borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  time: { fontSize: 14, color: '#4f46e5', fontWeight: '600' },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  badgeHigh: { backgroundColor: '#fee2e2' },
  badgeMed: { backgroundColor: '#fef3c7' },
  badgeLow: { backgroundColor: '#e0e7ff' },
  badgeText: { fontSize: 11, fontWeight: '600', writingDirection: 'rtl' },
  taskTitle: { fontSize: 18, fontWeight: '600', marginTop: 8, writingDirection: 'rtl' },
  building: { color: '#64748b', marginTop: 4, writingDirection: 'rtl' },
  actions: { flexDirection: 'row', gap: 8, marginTop: 12 },
  action: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: '#e2e8f0' },
  actionPrimary: { backgroundColor: '#10b981', borderColor: '#10b981' },
  actionText: { color: '#4f46e5', fontWeight: '600', writingDirection: 'rtl' },
});
