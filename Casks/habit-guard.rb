# Created by scripts/make_package_manifests.py from packaging/templates; do not edit by hand.
cask "habit-guard" do
  version "0.1.0"
  sha256 "3cef98798da748ea5c4028619a5e30ca78b6d163a1e2c9219458199fcdb06ef2"

  url "https://github.com/bugraskl/habit-guard/releases/download/v#{version}/HabitGuard-#{version}-macos-arm64.dmg"
  name "Habit Guard"
  desc "Catches nail biting and similar habits through your webcam"
  homepage "https://bugraskl.github.io/habit-guard/"

  livecheck do
    url :url
    strategy :github_latest
  end

  depends_on arch: :arm64
  depends_on macos: :sonoma

  app "Habit Guard.app"

  zap trash: [
    "~/Library/Application Support/habit-guard",
    "~/Library/LaunchAgents/io.github.bugraskl.habit-guard.plist",
  ]

  caveats <<~EOS
    Habit Guard is not signed with an Apple Developer ID yet. If macOS refuses to open it, right-click
    the app in Applications, choose Open, and allow the camera when asked.
  EOS
end
