const MP_PHOTO = '/mp-lavu-sri-krishna-devarayalu.jpg';

const DETAILS = [
  { label: 'Constituency', value: 'Narasaraopet Lok Sabha' },
  { label: 'State', value: 'Andhra Pradesh' },
  { label: 'District', value: 'Palnadu district' },
  { label: 'Political Party', value: 'Telugu Desam Party (TDP)' },
];

export default function ProfilePage() {
  return (
    <div className="max-w-3xl mx-auto space-y-6 page-enter">
      <div>
        <h2 className="text-lg font-bold text-primary">Constituency Profile</h2>
        <p className="text-sm text-muted">Member of Parliament · Narasaraopet</p>
      </div>

      <section className="rounded-2xl border border-app bg-surface shadow-soft overflow-hidden">
        <div className="flex flex-col sm:flex-row gap-6 p-6 sm:p-8">
          <div className="shrink-0 mx-auto sm:mx-0">
            <img
              src={MP_PHOTO}
              alt="Lavu Sri Krishna Devarayalu, Member of Parliament for Narasaraopet"
              className="h-44 w-44 sm:h-52 sm:w-52 rounded-2xl object-cover object-top border border-app shadow-soft bg-secondary"
            />
          </div>
          <div className="min-w-0 flex-1 space-y-4 text-center sm:text-left">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-primary">
                Member of Parliament
              </p>
              <h1 className="mt-1 text-2xl sm:text-3xl font-bold text-app tracking-tight">
                Lavu Sri Krishna Devarayalu
              </h1>
              <p className="mt-2 text-sm text-muted leading-relaxed">
                The Member of Parliament (MP) for the Narasaraopet Lok Sabha constituency in
                Andhra Pradesh.
              </p>
            </div>

            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              {DETAILS.map((row) => (
                <div
                  key={row.label}
                  className="rounded-xl border border-app bg-secondary/60 px-3.5 py-2.5 text-left"
                >
                  <dt className="text-xs font-medium text-muted">{row.label}</dt>
                  <dd className="mt-0.5 font-semibold text-app">{row.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>
    </div>
  );
}
