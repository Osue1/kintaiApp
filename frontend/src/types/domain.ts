/**
 * 画面用ドメイン型。
 *
 * Phase 1〜5 の API が未実装のため、当面は stores/*.ts がこの型でモックデータを返す。
 * バックエンドが用意でき次第、stores 内の実装だけを api 呼び出しに差し替える想定。
 */

export type PunchState = 'not_started' | 'working' | 'finished'

export interface TodayPunch {
  date: string
  state: PunchState
  clockInAt: string | null
  clockOutAt: string | null
}

export type DailyRecordNote = 'normal' | 'pending' | 'leave' | 'holiday'

export interface DailyRecord {
  date: string
  weekday: string
  clockIn: string | null
  clockOut: string | null
  workedMinutes: number | null
  note: DailyRecordNote
}

export interface MonthlySummary {
  workDays: number
  workedHours: number
  overtimeHours: number
  overtimeLimitHours: number
  paidLeaveRemaining: number
}

export type NotificationCategory = 'approval' | 'reminder' | 'info'

export interface AppNotification {
  id: string
  category: NotificationCategory
  title: string
  detail: string
  createdAt: string
  read: boolean
}

export interface CorrectionRequestPayload {
  date: string
  type: 'clock_in' | 'clock_out'
  correctedTime: string
  reason: string
}

export type LeaveUnit = 'full' | 'half_am' | 'half_pm'

export interface LeaveType {
  id: string
  name: string
  paid: boolean
  supportsHalfDay: boolean
  requiresReason: boolean
}

export interface LeaveBalance {
  paidTotal: number
  paidUsed: number
  paidRemaining: number
  carryOver: number
  nextGrant: { date: string; days: number }
  mandatoryFiveDays: { used: number; required: number; deadline: string }
  others: { typeId: string; typeName: string; remaining: number | null }[]
}

export type LeaveRequestStatus = 'pending' | 'approved' | 'rejected'

export interface LeaveRequest {
  id: string
  typeId: string
  typeName: string
  startDate: string
  endDate: string
  unit: LeaveUnit
  days: number
  reason: string
  status: LeaveRequestStatus
  appliedAt: string
  rejectedReason?: string
}

export interface LeaveRequestPayload {
  typeId: string
  startDate: string
  endDate: string
  unit: LeaveUnit
  reason: string
}

// --- 管理者: 勤怠承認 ---

export type ApprovalType = 'leave' | 'correction' | 'monthly'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

export interface ApprovalItem {
  id: string
  employeeName: string
  type: ApprovalType
  summary: string
  detail: string
  requestedAt: string
  status: ApprovalStatus
  rejectedReason?: string
}

// --- 管理者: 有給・残業アラート ---

export interface PaidLeaveAlertEntry {
  employeeId: string
  employeeName: string
  grantedDate: string
  used: number
  required: number
  deadline: string
}

export type OvertimeAlertSeverity = 'warning' | 'critical' | 'violation'

export interface OvertimeAlertReason {
  kind: string
  label: string
  severity: OvertimeAlertSeverity
}

export interface OvertimeAlertEntry {
  employeeId: string
  employeeName: string
  month: string
  overtimeHours: number
  limitHours: number
  severity: OvertimeAlertSeverity
  reasons: OvertimeAlertReason[]
}

// --- 管理者: 外注管理 ---

export type ContractorRateType = 'hourly' | 'daily' | 'fixed'

export interface Contractor {
  id: string
  name: string
  email: string
  rateType: ContractorRateType
  rateAmount: number
  closingDay: number
  paymentMonthOffset: 0 | 1
  paymentDay: number
}

export interface ContractorPayload {
  name: string
  email: string
  rateType: ContractorRateType
  rateAmount: number
  closingDay: number
  paymentMonthOffset: 0 | 1
  paymentDay: number
}

export interface ContractorWorkRecord {
  id: string
  contractorId: string
  yearMonth: string
  hours: number | null
  days: number | null
  fixedApplied: boolean
  note: string
  enteredAt: string
}

export interface ContractorWorkRecordPayload {
  contractorId: string
  yearMonth: string
  hours: number | null
  days: number | null
  fixedApplied: boolean
  note: string
}

// --- 管理者: 請求書・支払調書 ---

export type InvoiceStatus = 'draft' | 'issued' | 'sent' | 'void'

export interface Invoice {
  id: string
  invoiceNo: string
  contractorId: string
  contractorName: string
  yearMonth: string
  quantityLabel: string
  subtotal: number
  tax: number
  withholding: number
  payable: number
  status: InvoiceStatus
  issuedAt: string
  sentAt?: string
  confirmDeadline: string | null
  confirmedAt: string | null
  confirmMethod: 'manual' | 'deemed_after_deadline' | null
}

export interface WithholdingStatement {
  id: string
  contractorId: string
  contractorName: string
  year: number
  totalPayment: number
  totalWithholding: number
}

// --- 管理者: 従業員管理 ---

export type EmployeeRole = 'admin' | 'employee'

export interface Employee {
  id: string
  email: string
  name: string
  role: EmployeeRole
  isAdmin: boolean
  hireDate: string | null
  retiredAt: string | null
  isActive: boolean
  teamId: string | null
  teamName: string | null
  workPatternId: string | null
  workPatternName: string | null
  leavePolicyId: string | null
  leavePolicyName: string | null
}

export interface EmployeeOption {
  id: string
  name: string
}

export interface EmployeeCreatePayload {
  email: string
  name: string
  password: string
  role: EmployeeRole
  hireDate: string | null
  teamId: string | null
  workPatternId: string | null
  leavePolicyId: string | null
}

export interface EmployeeUpdatePayload {
  name?: string
  role?: EmployeeRole
  hireDate?: string | null
  retiredAt?: string | null
  isActive?: boolean
  teamId?: string | null
  workPatternId?: string | null
  leavePolicyId?: string | null
  password?: string
}

// --- 他社員の出勤状況 ---

export type TeamStatusScope = 'team' | 'all'

export interface TeamMemberStatus {
  id: string
  name: string
  teamName: string | null
  isAdmin: boolean
  state: PunchState
  clockInAt: string | null
  clockOutAt: string | null
  onLeave: boolean
}

export interface TeamStatusResult {
  scope: TeamStatusScope
  fallbackToAll: boolean
  teamName: string | null
  members: TeamMemberStatus[]
}

// --- 勤怠明細・月次締め申請 ---

export type MonthlyStatus = 'draft' | 'submitted' | 'approved'

export interface MonthlyDetail {
  yearMonth: string
  status: MonthlyStatus
  locked: boolean
  totals: { workDays: number; workedHours: number; overtimeHours: number }
  days: DailyRecord[]
}

// --- 管理者: 年次有給休暇管理簿 ---

export interface LeaveLedgerConsumption {
  dateLabel: string
  days: number
  leaveTypeName: string
}

export interface LeaveLedgerGrant {
  grantedOn: string
  days: number
  expiresOn: string
  consumed: number
  remaining: number
  isExpired: boolean
  consumptions: LeaveLedgerConsumption[]
}

export interface LeaveLedger {
  employee: { id: string; name: string; hireDate: string | null }
  grants: LeaveLedgerGrant[]
}

// --- 管理者: 監査ログ ---

export interface AuditLogEntry {
  id: number
  actorName: string | null
  action: string
  targetType: string
  targetId: number | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  ip: string | null
  userAgent: string
  createdAt: string
}

export interface AuditLogFilter {
  action?: string
  targetType?: string
  dateFrom?: string
  dateTo?: string
}
